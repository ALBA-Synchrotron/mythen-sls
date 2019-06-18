import struct
import logging
import functools

import numpy
import gevent.server

from .protocol import (DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT, INET_TEMPLATE,
                       GET_CODE,
                       ResultType, CommandCode, DetectorSettings,
                       DetectorType, TimerType, RunStatus,
                       read_command, read_i32, read_i64)

log = logging.getLogger('SLSServer')

DEFAULT_DETECTOR_CONFIG = {
    DetectorType.MYTHEN: dict(nb_mods_x=6, nb_mods_y=1,
                              nb_channels_x=128, nb_channels_y=1,
                              nb_chips_x=10, nb_chips_y=1,
                              nb_dacs=6, nb_adcs=0, dynamic_range=24,
                              energy_threshold=-100,
                              nb_frames=0,
                              acquisition_time=int(1e9),
                              frame_period=0,
                              delay_after_trigger=0,
                              nb_gates=0,
                              nb_probes=0,
                              nb_cycles=0,
                              settings=DetectorSettings.STANDARD,
                              type=DetectorType.MYTHEN)
}


def sanitize_config(config):
    config.setdefault('ctrl_port', DEFAULT_CTRL_PORT)
    config.setdefault('stop_port', DEFAULT_STOP_PORT)
    dtype = DetectorType(config.get('type', DetectorType.MYTHEN))
    result = dict(DEFAULT_DETECTOR_CONFIG[dtype])
    result.update(config)
    result['settings'] = DetectorSettings(result['settings'])
    return result


class Detector:

    def __init__(self, config):
        self.config = config
        self.run_status = RunStatus.IDLE
        self.last_client = (None, 0)

    def __getitem__(self, name):
        if isinstance(name, str):
            try:
                return self.config[name]
            except KeyError:
                return getattr(self, name)
        return [self[i] for i in name]

    def __setitem__(self, name, value):
        if name in self.config:
            self.config[name] = value
        else:
            setattr(self, name, value)

    @property
    def last_client_ip(self):
        return self.last_client[0] or '0.0.0.0'

    @property
    def nb_modules(self):
        return self.config['nb_mods_x'] * self.config['nb_mods_y']

    @property
    def nb_chips(self):
        return self.config['nb_chips_x'] * self.config['nb_chips_y']

    @property
    def nb_channels(self):
        return self.config['nb_channels_x'] * self.config['nb_channels_y']

    @property
    def data_bytes(self):
        drange = self['dynamic_range']
        drangeb = 4 if drange == 24 else int(drange/8)
        return self.nb_modules * self.nb_chips * self.nb_channels * drangeb

    def handle_ctrl(self, sock, addr):
        log.debug('connected to control %r', addr)
        try:
            self._handle_ctrl(sock, addr)
        except ConnectionError:
            log.warning('unpolite client disconnected from control %r', addr)
        except:
            log.exception('error handling control request from %r', addr)
        log.debug('finished control %r', addr)

    def _handle_ctrl(self, sock, addr):
        conn = sock.makefile(mode='rwb')
        if addr[0] == self.last_client[0]:
            result_type = ResultType.OK
        else:
            result_type = ResultType.FORCE_UPDATE
        cmd = read_command(conn)
        cmd_lower = cmd.name.lower()
        log.info('control request: %s', cmd)
        func = getattr(self, cmd_lower)
        result = func(conn, addr)
        # result == None => function handles all replies
        if result is not None:
            sock.sendall(struct.pack('<i', result_type))
            sock.sendall(result)
        sock.close()

    def handle_stop(self, sock, addr):
        log.debug('connected to stop %r', addr)
        try:
            self._handle_stop(sock, addr)
        except ConnectionError:
            log.warning('unpolite client disconnected from stop %r', addr)
        except:
            log.exception('error handling stop request from %r', addr)
        log.debug('finished stop %r', addr)

    def _handle_stop(self, sock, addr):
        conn = sock.makefile(mode='rwb')
        result_type = ResultType.OK
        cmd = read_command(conn)
        cmd_lower = cmd.name.lower()
        log.info('control request: %s', cmd)
        func = getattr(self, cmd_lower)
        result = func(conn, addr)
        # result == None => function handles all replies
        if result is not None:
            sock.sendall(struct.pack('<i', result_type))
            sock.sendall(result)
        sock.close()

    def stop_acquisition(self, conn, addr):
        conn.write(struct.pack('<i', ResultType.OK))

    def get_run_status(self, conn, addr):
        return struct.pack('<i', self.run_status)

    def get_detector_type(self, conn, addr):
        return struct.pack('<i', self['type'])

    def get_energy_threshold(self, conn, addr):
        mod_nb = read_i32(conn)
        value = self['energy_threshold']
        log.info('get energy threshold(module=%d) = %d', mod_nb, value)
        return struct.pack('<i', value)

    def set_energy_threshold(self, conn, addr):
        value = read_i32(conn)
        mod_nb = read_i32(conn)
        settings = read_i32(conn)
        self['energy_threshold'] = value
        log.info('set energy threshold(module=%d, value=%d, settings=%d)',
                 mod_nb, value, settings)
        return struct.pack('<i', self['energy_threshold'])

    def update_client(self, conn, addr):
        result_type = ResultType.OK
        last_client_ip = INET_TEMPLATE.format(self.last_client_ip)
        last_client_ip = last_client_ip.encode('ascii')
        field_names = ('nb_modules',
                       'nb_modules', # TODO: don't know what it is
                       'dynamic_range', 'data_bytes',
                       'settings', 'energy_threshold', 'nb_frames',
                       'acquisition_time', 'frame_period',
                       'delay_after_trigger', 'nb_gates', 'nb_probes',
                       'nb_cycles')
        fields = [last_client_ip] + self[field_names]
        self.last_client = addr
        return struct.pack('<16siiiiiiqqqqqqq', *fields)

    def timer(self, conn, addr):
        param = TimerType(read_i32(conn))
        name = param.name.lower()
        value = read_i64(conn)
        if value != GET_CODE:
            self[name] = value
        result = self[name]
        log.info('%s timer %r = %r', 'get' if value == GET_CODE else 'set',
                 param.name, result)
        return struct.pack('<q', result)

    def start_and_read_all(self, conn, addr):
        self.run_status = RunStatus.RUNNING
        nb_cycles = max(self['nb_cycles'], 1)
        nb_frames = max(self['nb_frames'], 1)
        acq_time = self['acquisition_time']*1e-9
        dead_time = self['frame_period']*1e-9
        size = int(self.data_bytes / 4)
        finished_msg = struct.pack('<i', ResultType.FINISHED) + \
                           b'acquisition successfully finished'
        last = nb_cycles * nb_frames
        n = 0
        for cycle_index in range(nb_cycles):
            for frame_index in range(nb_frames):
                is_last = n == (last - 1)
                gevent.sleep(acq_time)
                data = numpy.full((size,), cycle_index*frame_index+10,
                                  dtype='<i4')
                log.info('writting cycle #%d, frame #%d',
                         cycle_index, frame_index)
                buff = struct.pack('<i', ResultType.OK) + data.tobytes()
                if is_last:
                    buff += finished_msg
                conn.write(buff)
                if dead_time:
                    gevent.sleep(dead_time)
                n += 1
        self.run_status = RunStatus.IDLE


def run(config):
    config = sanitize_config(config)
    ctrl_port = config['ctrl_port']
    stop_port = config['stop_port']
    detector = Detector(config)
    ctrl = gevent.server.StreamServer(('0.0.0.0', ctrl_port),
                                      detector.handle_ctrl)
    stop = gevent.server.StreamServer(('0.0.0.0', stop_port),
                                      detector.handle_stop)
    tasks = [gevent.spawn(s.serve_forever) for s in [ctrl, stop]]
    log.info('Ready to accept requests')
    gevent.joinall(tasks)
#    server.serve_forever()


def main(args=None):
    fmt = '%(levelname)s %(asctime)-15s %(name)s: %(message)s'
    logging.basicConfig(format=fmt, level='DEBUG')
    config = dict(ctrl_port=DEFAULT_CTRL_PORT)
    try:
        run(config)
    except KeyboardInterrupt:
        log.info('Ctrl-C pressed. Bailing out')


if __name__ == '__main__':
    main()
