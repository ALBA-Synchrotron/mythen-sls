import os
import time
import struct
import logging
import functools

import numpy
import scipy.stats

import gevent.queue
import gevent.server

from .protocol import (DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT, INET_TEMPLATE,
                       GET_CODE,
                       IdParam, ResultType, CommandCode, DetectorSettings,
                       DetectorType, TimerType, SpeedType,
                       SynchronizationMode, MasterMode,
                       ExternalCommunicationMode, ExternalSignal,
                       RunStatus, Dimension, ReadoutFlag,
                       read_command, read_format, read_i32, read_i64)

log = logging.getLogger('SLSServer')


def build_default_module(nb, serial_nb):
    return dict(id=nb, serial_nb=serial_nb,
                settings=DetectorSettings.STANDARD,
                gain=0, offset=0,
                dacs=list(range(nb, 6+nb)), adcs=[],
                chips=[dict(register=0, channels=list(range(nb+idx, 128+nb+idx)))
                       for idx in range(10)])


DEFAULT_DETECTOR_CONFIG = {
    DetectorType.MYTHEN: dict(
        module_firmware_version=0x543543,
        detector_serial_number=0x66778899,
        detector_firmware_version=0xa943f9,
        detector_software_version=0x1c7e94,
        receiver_version=0,
        nb_modules_x=6, nb_modules_y=1,
        nb_modules_x_max=6,
        nb_channels_x=128, nb_channels_y=1,
        nb_chips_x=10, nb_chips_y=1,
        nb_dacs=6, nb_adcs=0, dynamic_range=32, # when dr = 24 put 32 go figure!
        energy_threshold=9071,
        nb_frames=0,
        acquisition_time=int(1e9),
        frame_period=0,
        delay_after_trigger=0,
        nb_gates=0,
        nb_probes=0,
        nb_cycles=0,
        settings=DetectorSettings.STANDARD,
        type=DetectorType.MYTHEN,
        clock_divider=6,
        wait_states=13,
        tot_clock_divider=4,
        tot_duty_cycle=0,
        signal_length=3,
        external_communication_mode=ExternalCommunicationMode.AUTO_TIMING,
        external_signal=ExternalSignal.SIGNAL_OFF,
        external_signals=4*[ExternalSignal.GATE_OUT_ACTIVE_HIGH,
                            ExternalSignal.TRIGGER_IN_RISING_EDGE,
                            ExternalSignal.SIGNAL_OFF,
                            ExternalSignal.SIGNAL_OFF],
        synchronization_mode=SynchronizationMode.NO_SYNCHRONIZATION,
        master_mode=MasterMode.NO_MASTER,
        readout_flags=ReadoutFlag.NORMAL_READOUT,
        modules=[build_default_module(idx, 0xEE0+idx) for idx in range(10)]
    )
}


def sanitize_config(config):
    config.setdefault('ctrl_port', DEFAULT_CTRL_PORT)
    config.setdefault('stop_port', DEFAULT_STOP_PORT)
    dtype = DetectorType(config.get('type', DetectorType.MYTHEN))
    result = dict(DEFAULT_DETECTOR_CONFIG[dtype])
    result.update(config)
    result['settings'] = DetectorSettings(result['settings'])
    result['lock_server'] = 0
    return result


def normal(nb_points=1280, scale=1000_000, offset=100, width=100, loc=None):
    if loc is None:
        # middle
        loc = int(nb_points / 2)
    x = numpy.arange(nb_points)
    y = scipy.stats.norm.pdf(numpy.arange(nb_points), loc=loc,
                             scale=width) * scale + offset
    return y.astype('<i4')


class Acquisition:

    def __init__(self, detector):
        self.detector = detector
        self.task = None
        self.frames = gevent.queue.Queue()
        self.run_status = RunStatus.IDLE

    def prepare(self):
        detector = self.detector
        self.params = dict(nb_frames=max(detector['nb_frames'], 1),
                           nb_cycles=max(detector['nb_cycles'], 1),
                           acquisition_time=detector['acquisition_time']*1e-9,
                           dead_time=detector['frame_period']*1e-9,
                           size=int(self.detector.data_bytes / 4))
        self.nb_frames_left = self.params['nb_frames'] * self.params['nb_cycles']
        self.nb_cycles_left = self.params['nb_cycles']

    @property
    def acquisition_time_left(self):
        frame_elapsed = time.time() - self.frame_start
        return self.params['acquisition_time'] - frame_elapsed

    def start(self):
        self.task = gevent.spawn(self.run)

    def run(self):
        self.run_status = RunStatus.RUNNING
        for frames in self.gen_frames():
            self.frames.put(frames)
        self.frames.put(None)
        self.run_status = RunStatus.IDLE

    def gen_frames(self):
        nb_cycles = self.params['nb_cycles']
        nb_frames = self.params['nb_frames']
        acq_time = self.params['acquisition_time']
        dead_time = self.params['dead_time']
        size = self.params['size']
        start_time = time.time()
        n = 0
        for cycle_index in range(nb_cycles):
            for frame_index in range(nb_frames):
                is_last = self.nb_frames_left == 1
                self.frame_start = time.time()
                nap = start_time + (acq_time + dead_time) * n + acq_time - time.time()
                if nap > 0:
                    gevent.sleep(nap)
                data = normal(size, scale=1_000_000 * (cycle_index+1)*(frame_index+1))
                data += normal(size, scale=300_000 * (cycle_index+1)*(frame_index+1), loc=800)
                data += normal(size, scale=50_000 * (cycle_index+1)*(frame_index+1), loc=5000)
                data += normal(size, scale=800_000 * (cycle_index+1)*(frame_index+1), width=200, loc=6500)
                data += numpy.random.randint(0, 100, size, '<i4') # noise
                events = [ResultType.OK, data]
                if is_last:
                    events.append(ResultType.FINISHED)
                    events.append(b'acquisition successfully finished')
                self.detector.log.info('sending frame #%d for cycle #%d',
                                       frame_index, cycle_index)
                yield events
                self.nb_frames_left -= 1
                if dead_time:
                    gevent.sleep(dead_time)
                n += 1
            self.nb_cycles_left -= 1

    def stop(self):
        if self.task is not None:
            self.task.kill()


class Detector:

    def __init__(self, config):
        self.config = config
        self._run_status = RunStatus.IDLE
        self.acquisition = None
        self._reset_status
        self.last_client = (None, 0)
        self.servers = []
        self.start_time = time.time()
        self.log = log.getChild('{}({})'.format(type(self).__name__,
                                                config['name']))

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

    def _reset_status(self, status):
        status.update(dict(
            nb_frames=self['nb_frames'],
            acquisition_time=self['acquisition_time'],
            frame_period=self['frame_period'],
            delay_after_trigger=self['delay_after_trigger'],
            nb_gates=self['nb_gates'],
            nb_probes=self['nb_probes'],
            nb_cycles=self['nb_cycles'],
        ))

    @property
    def client_ip(self):
        return self.last_client[0] or '0.0.0.0'

    @property
    def nb_mods(self):
        return self.config['nb_modules_x'] * self.config['nb_modules_y']

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
        return self.nb_mods * self.nb_chips * self.nb_channels * drangeb

    def handle_ctrl(self, sock, addr):
        self.log.debug('connected to control %r', addr)
        try:
            self._handle_ctrl(sock, addr)
        except ConnectionError:
            self.log.debug('unpolite client disconnected from control %r', addr)
        except:
            self.log.exception('error handling control request from %r', addr)
        self.log.debug('finished control %r', addr)

    def _handle_ctrl(self, sock, addr):
        conn = sock.makefile(mode='rwb')
        if addr[0] == self.last_client[0]:
            result_type = ResultType.OK
        else:
            result_type = ResultType.FORCE_UPDATE
        cmd = read_command(conn)
        cmd_lower = cmd.name.lower()
        self.log.info('control request: %s', cmd)
        try:
            func = getattr(self, cmd_lower)
            result = func(conn, addr)
        except Exception as e:
            result_type = ResultType.FAIL
            result = '{}: {}\x00'.format(type(e).__name__, e).encode('ascii')
            self.log.exception('error handling control request from %r', addr)
        # result == None => function handles all replies
        if result is not None:
            sock.sendall(struct.pack('<i', result_type))
            sock.sendall(result)
        sock.close()

    def handle_stop(self, sock, addr):
        self.log.debug('connected to stop %r', addr)
        try:
            self._handle_stop(sock, addr)
        except ConnectionError:
            self.log.debug('unpolite client disconnected from stop %r', addr)
        except:
            self.log.exception('error handling stop request from %r', addr)
        self.log.debug('finished stop %r', addr)

    def _handle_stop(self, sock, addr):
        conn = sock.makefile(mode='rwb')
        result_type = ResultType.OK
        cmd = read_command(conn)
        cmd_lower = cmd.name.lower()
        self.log.info('stop request: %s', cmd)
        try:
            func = getattr(self, cmd_lower)
            result = func(conn, addr)
        except Exception as e:
            result_type = ResultType.FAIL
            result = '{}: {}\x00'.format(type(e).__name__, e).encode('ascii')
            self.log.exception('error handling stop request from %r', addr)
        # result == None => function handles all replies
        if result is not None:
            sock.sendall(struct.pack('<i', result_type))
            sock.sendall(result)
        sock.close()

    def stop_acquisition(self, conn, addr):
        conn.write(struct.pack('<i', ResultType.OK))
        conn.flush()

    def last_client_ip(self, conn, addr):
        ip = INET_TEMPLATE.format(self.client_ip).encode('ascii')
        return struct.pack('<16s', ip)

    def get_id(self, conn, addr):
        param = IdParam(read_i32(conn))
        name = param.name.lower()
        if name == 'module_serial_number':
            mod_nb = read_i32(conn)
            value = self['modules'][mod_nb]['serial_nb']
            self.log.info('get id %s[%d] = %d', param.name, mod_nb, value)
        else:
            value = self[name]
            self.log.info('get id %s = %d', param.name, value)

        return struct.pack('<q', value)

    def get_module(self, conn, addr):
        mod_nb = read_i32(conn)
        self.log.info('get module[%d]', mod_nb)
        mod_config = self['modules'][mod_nb]
        dacs, adcs, chips = mod_config['dacs'], mod_config['adcs'], mod_config['chips']
        nb_dacs, nb_adcs, nb_chips = len(dacs), len(adcs), len(chips)
        nb_channels = sum(len(chip['channels']) for chip in chips)
        result = struct.pack('<iiiiiii', mod_config['id'], mod_config['serial_nb'],
                             nb_channels, nb_chips, nb_dacs, nb_adcs,
                             mod_config['settings'])
        if nb_dacs:
            result += struct.pack('<{}i'.format(nb_dacs), *dacs)
        if nb_adcs:
            result += struct.pack('<{}i'.format(nb_adcs), *adcs)
        result += struct.pack('<{}i'.format(nb_chips), *[chip['register'] for chip in chips])
        result += struct.pack('<{}i'.format(nb_channels),
                              *[ch for chip in chips for ch in chip['channels']])
        result += struct.pack('<dd', mod_config['gain'], mod_config['offset'])
        return result

    def set_module(self, conn, addr):
        fields = read_format(conn, '<iiiiiii')
        mod_nb = fields[0]
        self.log.info('set module[%d]', mod_nb)
        nb_channels, nb_chips, nb_dacs, nb_adcs = fields[2:6]
        mod = dict(id=mod_nb, serial_nb=fields[1], settings=fields[6])
        # garbage: don't know why the client sends its private pointers
        fields = read_format(conn, '<iiii')
        mod['gain'], mod['offset'] = read_format(conn, '<dd')
        mod['dacs'] = read_format(conn, '<{}i'.format(nb_dacs)) if nb_dacs else []
        mod['adcs'] = read_format(conn, '<{}i'.format(nb_adcs)) if nb_adcs else []
        chip_registers = read_format(conn, '<{}i'.format(nb_chips))
        channels = read_format(conn, '<{}i'.format(nb_channels))
        channels_per_chip = nb_channels // nb_chips
        mod['chips'] = chips = []
        for idx in range(nb_chips):
            chip = dict(register=chip_registers[idx],
                        channels=channels[idx*channels_per_chip:(idx+1)*channels_per_chip])
            chips.append(chip)
        mod_config = self['modules'][mod_nb]
        mod_config.update(mod)
        return struct.pack('<i', mod_nb)

    def run_status(self, conn, addr):
        return struct.pack('<i', self._run_status)

    def detector_type(self, conn, addr):
        return struct.pack('<i', self['type'])

    def get_energy_threshold(self, conn, addr):
        mod_nb = read_i32(conn)
        value = self['energy_threshold']
        self.log.info('get energy threshold(module=%d) = %d', mod_nb, value)
        return struct.pack('<i', value)

    def set_energy_threshold(self, conn, addr):
        value = read_i32(conn)
        mod_nb = read_i32(conn)
        settings = read_i32(conn)
        self['energy_threshold'] = value
        self.log.info('set energy threshold(module=%d, value=%d, settings=%d)',
                 mod_nb, value, settings)
        return struct.pack('<i', self['energy_threshold'])

    def update_client(self, conn, addr):
        result_type = ResultType.OK
        last_client_ip = INET_TEMPLATE.format(self.client_ip)
        last_client_ip = last_client_ip.encode('ascii')
        field_names = ('nb_modules_x',
                       'nb_modules_x_max',
                       'dynamic_range', 'data_bytes',
                       'settings', 'energy_threshold', 'nb_frames',
                       'acquisition_time', 'frame_period',
                       'delay_after_trigger', 'nb_gates', 'nb_probes',
                       'nb_cycles')
        fields = [last_client_ip] + self[field_names]
        self.last_client = addr
        return struct.pack('<16siiiiiiqqqqqqq', *fields)

    def timer(self, conn, addr):
        timer_type = TimerType(read_i32(conn))
        name = timer_type.name.lower()
        value = read_i64(conn)
        if value != GET_CODE:
            self[name] = value
        if timer_type == TimerType.ACTUAL_TIME:
            result = int((time.time() - start_time)*1E9)
        else:
            result = self[name]
        self.log.info('%s timer %r = %r', 'get' if value == GET_CODE else 'set',
                      timer_type.name, result)
        return struct.pack('<q', result)

    def dynamic_range(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            self['dynamic_range'] = value
        result = self['dynamic_range']
        self.log.info('%s dynamic range = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def settings(self, conn, addr):
        value = read_i32(conn)
        mod_nb = read_i32(conn)
        if value != GET_CODE:
            self['modules'][mod_nb]['settings'] = value
        result = self['modules'][mod_nb]['settings']
        self.log.info('%s mod_settings[%d] = %r',
                      'get' if value == GET_CODE else 'set', mod_nb, result)
        return struct.pack('<i', result)

    def nb_modules(self, conn, addr):
        dimension = Dimension(read_i32(conn))
        value = read_i32(conn)
        name = 'nb_modules_' + dimension.name.lower()
        if value != GET_CODE:
            self[name] = value
        result = self[name]
        self.log.info('%s nb modules %r = %r',
                      'get' if value == GET_CODE else 'set', name, result)
        return struct.pack('<i', result)

    def readout_flags(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            value = ReadoutFlag(value)
            self['readout_flags'] = value
        result = self['readout_flags']
        self.log.info('%s readout flags = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def synchronization_mode(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            value = SyncronizationMode(value)
            self['synchronization_mode'] = value
        result = self['synchronization_mode']
        self.log.info('%s synchronization mode = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def master_mode(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            value = MasterMode(value)
            self['master_mode'] = value
        result = self['master_mode']
        self.log.info('%s master mode = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def external_communication_mode(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            value = ExternalCommunicationMode(value)
            self['external_communication_mode'] = value
        result = self['external_communication_mode']
        self.log.info('%s external communication mode = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def external_signal(self, conn, addr):
        index = read_i32(conn)
        value = read_i32(conn)
        global_sig = index == -1
        if value != GET_CODE:
            value = ExternalSignal(value)
            if global_sig:
                self['external_signal'] = value
            else:
                self['external_signals'][index] = value
        if global_sig:
            result = self['external_signal']
        else:
            result = self['external_signals'][index]
        self.log.info('%s external signal[%d] = %r',
                      'get' if value == GET_CODE else 'set', index, result)
        return struct.pack('<i', result)

    def speed(self, conn, addr):
        speed = SpeedType(read_i32(conn))
        name = speed.name.lower()
        value = read_i32(conn)
        if value != GET_CODE:
            self[name] = value
        result = self[name]
        self.log.info('%s speed %r = %r', 'get' if value == GET_CODE else 'set',
                      speed.name, result)
        return struct.pack('<i', result)

    def lock_server(self, conn, addr):
        value = read_i32(conn)
        if value != GET_CODE:
            self['lock_server'] = value
        result = self['lock_server']
        self.log.info('%s lock server = %r',
                      'get' if value == GET_CODE else 'set', result)
        return struct.pack('<i', result)

    def time_left(self, conn, addr):
        timer_type = TimerType(read_i32(conn))
        name = timer_type.name.lower()
        if self._run_status == RunStatus.IDLE:
            result = self[name]
        elif self._run_status == RunStatus.RUNNING:
            acq = self.acquisition
            if timer_type == TimerType.ACQUISITION_TIME:
                result = int(acq.acquisition_time_left * 1E9)
            elif timer_type == TimerType.NB_FRAMES:
                result = acq.nb_frames_left
            elif timer_type == TimerType.NB_CYCLES:
                result = acq.nb_cycles_left
        self.log.info('get time left %r = %r', timer_type.name, result)
        return struct.pack('<q', result)

    def start_and_read_all(self, conn, addr):
        self.log.info('start acquisition')
        self._run_status = RunStatus.RUNNING
        self.acquisition = Acquisition(self)
        self.acquisition.prepare()
        self.acquisition.start()
        try:
            for frames in self.acquisition.frames:
                if frames is None:
                    break
                events = []
                for frame in frames:
                    if isinstance(frame, ResultType):
                        event = struct.pack('<i', frame)
                    elif isinstance(frame, bytes):
                        event = frame
                    else:
                        event = frame.tobytes()
                    events.append(event)
                try:
                    conn.write(b''.join(events))
                except BrokenPipeError:
                    pass
        finally:
            self.acquisition.stop()
            self.acquisition = None
            self._run_status = RunStatus.IDLE
            self.log.info('finished acquisition')

    def start(self):
        ctrl_port = self['ctrl_port']
        stop_port = self['stop_port']

        ctrl = gevent.server.StreamServer(('0.0.0.0', ctrl_port),
                                          self.handle_ctrl)
        stop = gevent.server.StreamServer(('0.0.0.0', stop_port),
                                          self.handle_stop)
        tasks = [gevent.spawn(s.serve_forever) for s in [ctrl, stop]]
        self.servers = list(zip([ctrl, stop], tasks))
        self.log.info('Ready to accept requests')
        return self.servers

    def stop(self):
        for server, task in self.servers:
            server.stop()
        self.servers = []

    def serve_forever(self):
        servers = self.start()
        gevent.joinall([task for _, task in servers])


def load_config(filename):
    if not os.path.exists(filename):
        raise ValueError('configuration file does not exist')
    ext = os.path.splitext(filename)[-1]
    if ext.endswith('toml'):
        from toml import load
    elif ext.endswith('yml') or ext.endswith('.yaml'):
        import yaml
        def load(fobj):
            return yaml.load(fobj, Loader=yaml.Loader)
    elif ext.endswith('json'):
        from json import load
    elif ext.endswith('py'):
        # python only supports a single detector definition
        def load(fobj):
            r = {}
            exec(fobj.read(), None, r)
            return [r]
    else:
        raise NotImplementedError
    with open(filename)as fobj:
        return load(fobj)


def detectors(config):
    if isinstance(config, dict):
        config = [dict(item, name=key)
                  for key, item in config.items()]
    return [Detector(sanitize_config(item)) for item in config]


def start(detectors):
    return {detector:detector.start() for detector in detectors}


def stop(detectors):
    for detector in detectors:
        detector.stop()


def serve_forever(detectors):
    tasks = [task for det, serv_tasks in start(detectors).items()
             for serv, task in serv_tasks]
    try:
        gevent.joinall(tasks)
    except KeyboardInterrupt:
        log.info('Ctrl-C pressed. Bailing out')
    stop(detectors)


def run(filename):
    logging.info('preparing to run...')
    config = load_config(filename)
    dets = detectors(config)
    serve_forever(dets)


def main(args=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', help='configuration file',
                        dest='config_file',
                        default='./mythen.toml')
    parser.add_argument('--log-level', help='log level', type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'])

    options = parser.parse_args(args)

    log_level = getattr(logging, options.log_level.upper())
    log_fmt = '%(levelname)s %(asctime)-15s %(name)s: %(message)s'
    logging.basicConfig(level=log_level, format=log_fmt)
    run(options.config_file)


if __name__ == '__main__':
    main()
