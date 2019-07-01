"""
# SLS Mythen:
  ___ ___ ___ ___ ___ ___
 |___|___|___|___|___|___|  6 modules
                 /    \
                /      \
               /__    __\
               |__|..|__|  10 chips
              /    \
             /_    _\
             |_|..|_|  128 channels
"""

import socket
import logging
import functools

import numpy

from . import protocol
from .protocol import (DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT, SLSError,
                       TimerType, SpeedType, ResultType)


class Connection:

    def __init__(self, addr):
        self.addr = addr
        self.sock = None
        self.log = logging.getLogger('Connection({0[0]}:{0[1]})'.format(addr))

    def connect(self):
        sock = socket.socket()
        sock.connect(self.addr)
        self.reader = sock.makefile('rb')
        self.sock = sock

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def __repr__(self):
        return '{0}({1[0]}:{1[1]})'.format(type(self).__name__, self.addr)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, etype, evalue, etb):
        self.close()

    def write(self, buff):
        self.log.debug('send: %r', buff)
        self.sock.sendall(buff)

    def recv(self, size):
        data = self.sock.recv(size)
        if not data:
            self.close()
            raise ConnectionError('connection closed')
        self.log.debug('recv: %r', data)
        return data

    def read(self, size):
        data = self.reader.read(size)
        if not data:
            self.close()
            raise ConnectionError('connection closed')
        self.log.debug('read: %r', data)
        return data


class Detector:

    def auto_ctrl_connect(f):
        name = f.__name__
        is_update = name == 'update_client'
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            with self.conn_ctrl:
                result, reply = f(self, *args, **kwargs)
                if result == ResultType.FORCE_UPDATE and not is_update:
                    self.update_client()
                return reply
        return wrapper

    def auto_stop_connect(f):
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            with self.conn_stop:
                result, reply = f(self, *args, **kwargs)
                return reply
        return wrapper

    def __init__(self, host,
                 ctrl_port=DEFAULT_CTRL_PORT,
                 stop_port=DEFAULT_STOP_PORT):
        self.conn_ctrl = Connection((host, ctrl_port))
        self.conn_stop = Connection((host, stop_port))

    @auto_ctrl_connect
    def update_client(self):
        return protocol.update_client(self.conn_ctrl)

    @auto_ctrl_connect
    def get_id(self, mode, mod_nb=None):
        return protocol.get_id(self.conn_ctrl, mode, mod_nb=mod_nb)

    @auto_ctrl_connect
    def get_energy_threshold(self, mod_nb=0):
        return protocol.get_energy_threshold(self.conn_ctrl, mod_nb)

    @auto_ctrl_connect
    def get_synchronization(self):
        return protocol.get_synchronization(self.conn_ctrl)

    @auto_ctrl_connect
    def set_synchronization(self, value):
        return set_synchronization(self.conn_ctrl, value)

    synchronization = property(get_synchronization, set_synchronization)

    @auto_ctrl_connect
    def get_detector_type(self):
        return protocol.get_detector_type(self.conn_ctrl)

    detector_type = property(get_detector_type)

    @auto_ctrl_connect
    def get_module(self, mod_nb=0):
        return protocol.get_module(self.conn_ctrl, mod_nb)

    @auto_stop_connect
    def get_time_left(self, timer):
        return protocol.get_time_left(self.conn_stop, timer)

    @property
    def exposure_time_left(self):
        return self.get_time_left(TimerType.ACQUISITION_TIME)

    @property
    def nb_cycles_left(self):
        return self.get_time_left(TimerType.NB_CYCLES)

    @property
    def nb_frames_left(self):
        return self.get_time_left(TimerType.NB_FRAMES)

    @property
    def progress(self):
        return self.get_time_left(TimerType.PROGRESS)

    @property
    def measurement_time(self):
        return self.get_time_left(TimerType.MEASUREMENT_TIME)

    @property
    def detector_actual_time(self):
        return self.get_time_left(TimerType.ACTUAL_TIME)

    @auto_ctrl_connect
    def set_timer(self, timer, value):
        return protocol.set_timer(self.conn_ctrl, timer, value)

    @auto_ctrl_connect
    def get_timer(self, timer):
        return protocol.get_timer(self.conn_ctrl, timer)

    @property
    def exposure_time(self):
        return self.get_timer(TimerType.ACQUISITION_TIME)

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self.set_timer(TimerType.ACQUISITION_TIME, exposure_time)

    @property
    def nb_frames(self):
        return self.get_timer(TimerType.NB_FRAMES)

    @nb_frames.setter
    def nb_frames(self, nb_frames):
        self.set_timer(TimerType.NB_FRAMES, nb_frames)

    @property
    def nb_cycles(self):
        return self.get_timer(TimerType.NB_CYCLES)

    @nb_cycles.setter
    def nb_cycles(self, nb_cycles):
        self.set_timer(TimerType.NB_CYCLES, nb_cycles)

    @property
    def delay_after_trigger(self):
        return self.get_timer(TimerType.DELAY_AFTER_TRIGGER)

    @delay_after_trigger.setter
    def delay_after_trigger(self, delay_after_trigger):
        self.set_timer(TimerType.DELAY_AFTER_TRIGGER, delay_after_trigger)

    @property
    def frame_period(self):
        return self.get_timer(TimerType.FRAME_PERIOD)

    @frame_period.setter
    def frame_period(self, frame_period):
        self.set_timer(TimerType.FRAME_PERIOD, frame_period)

    @auto_ctrl_connect
    def get_master_mode(self):
        return protocol.get_master_mode(self.conn_ctrl)

    @auto_ctrl_connect
    def set_master_mode(self, master_mode):
        return protocol.set_master_mode(self.conn_ctrl, master_mode)

    master_mode = property(get_master_mode, set_master_mode)

    @auto_ctrl_connect
    def get_dynamic_range(self):
        return protocol.get_dynamic_range(self.conn_ctrl)

    @auto_ctrl_connect
    def set_dynamic_range(self, dynamic_range):
        return protocol.set_dynamic_range(self.conn_ctrl, dynamic_range)

    dynamic_range = property(get_dynamic_range, set_dynamic_range)

    @auto_ctrl_connect
    def get_lock_server(self):
        return protocol.get_lock_server(self.conn_ctrl)

    @auto_ctrl_connect
    def set_lock_server(self, lock_server):
        return protocol.set_lock_server(self.conn_ctrl, lock_server)

    lock_server = property(get_lock_server, set_lock_server)

    @auto_ctrl_connect
    def get_settings(self, mod_nb):
        return protocol.get_settings(self.conn_ctrl, mod_nb)

    @auto_stop_connect
    def get_run_status(self):
        return protocol.get_run_status(self.conn_stop)

    run_status = property(get_run_status)

    @auto_ctrl_connect
    def start_acquisition(self):
        return protocol.start_acquisition(self.conn_ctrl)

    @auto_stop_connect
    def stop_acquisition(self):
        return protocol.stop_acquisition(self.conn_stop)

    def acquire(self):
        info = self.update_client()
        frame_size = info['data_bytes']
        dynamic_range = info['dynamic_range']
        with self.conn_ctrl:
            for event in protocol.start_and_read_all(self.conn_ctrl,
                                                     frame_size,
                                                     dynamic_range):
                yield event

    def read_all(self):
        info = self.update_client()
        frame_size = info['data_bytes']
        dynamic_range = info['dynamic_range']
        with self.conn_ctrl:
            for event in protocol.read_all(self.conn_ctrl, frame_size, dynamic_range):
                yield event

    def read_frame(self, frame_size=None, dynamic_range=None):
        if frame_size is None or dynamic_range is None:
            info = self.update_client()
        frame_size = frame_size or info['data_bytes']
        dynamic_range = dynamic_range or info['dynamic_range']
        with self.conn_ctrl:
            return protocol.read_frame(self.conn_ctrl, frame_size, dynamic_range)

    @auto_ctrl_connect
    def get_readout(self):
        return protocol.get_readout(self.conn_ctrl)

    @auto_ctrl_connect
    def set_readout(self, value):
        return protocol.set_readout(self.conn_ctrl, value)

    readout = property(get_readout, set_readout)

    @auto_ctrl_connect
    def get_rois(self):
        return protocol.get_rois(self.conn_ctrl)

    rois = property(get_rois)

    @auto_ctrl_connect
    def get_speed(self, speed_type):
        return protocol.get_speed(self.conn_ctrl, speed_type)

    @auto_ctrl_connect
    def set_speed(self, speed_type, value):
        return protocol.set_speed(self.conn_ctrl, speed_type, value)

    def get_clock_divider(self):
        return self.get_speed(SpeedType.CLOCK_DIVIDER)

    def set_clock_divider(self, value):
        return self.set_speed(SpeedType.CLOCK_DIVIDER, value)

    clock_divider = property(get_clock_divider, set_clock_divider)

    def get_wait_states(self):
        return self.get_speed(SpeedType.WAIT_STATES)

    def set_wait_states(self, value):
        return self.set_speed(SpeedType.WAIT_STATES, value)

    wait_states = property(get_wait_states, set_wait_states)

    def get_tot_clock_divider(self):
        return self.get_speed(SpeedType.TOT_CLOCK_DIVIDER)

    def set_tot_clock_divider(self, value):
        return self.set_speed(SpeedType.TOT_CLOCK_DIVIDER, value)

    tot_clock_divider = property(get_tot_clock_divider, set_tot_clock_divider)

    def get_tot_duty_cycle(self):
        return self.get_speed(SpeedType.TOT_DUTY_CYCLE)

    def set_tot_duty_cycle(self, value):
        return self.set_speed(SpeedType.TOT_DUTY_CYCLE, value)

    tot_duty_cycle = property(get_tot_duty_cycle, set_tot_duty_cycle)

    def get_signal_length(self):
        return self.get_speed(SpeedType.SIGNAL_LENGTH)

    def set_signal_length(self, value):
        return self.set_speed(SpeedType.SIGNAL_LENGTH, value)

    signal_length = property(get_signal_length, set_signal_length)

    @property
    @auto_ctrl_connect
    def last_client_ip(self):
        return protocol.get_last_client_ip(self.conn_ctrl)


def _acquire(detector, exposure_time=1, nb_frames=1, nb_cycles=1):
    detector.exposure_time = exposure_time
    detector.nb_frames = nb_frames
    detector.nb_cycles = nb_cycles
    for frame in detector.acquire():
        yield frame


def acquire(detector, exposure_time=1, nb_frames=1, nb_cycles=1, plot=False):
    if plot:
        nb_points = 1280 * 6 #TODO: calculate for specific detector
        from matplotlib import pyplot
        line = pyplot.plot(range(nb_points), nb_points*[0])[0]
    data = []
    for frame in _acquire(detector, exposure_time, nb_frames, nb_cycles):
        data.append(frame)
        if plot:
            line.set_ydata(frame)
    return data


# bad channels: list of bad channels
def load_bad_channels(fname):
    return numpy.loadtxt(fname, dtype=int)


def load_calibration(fname):
    with open(fname, 'rt') as fobj:
        data = fobj.read()
    offset, gain = data.strip().split()
    return float(offset), float(gain)


def load_module_settings(fname, nb_dacs=6, nb_channels=128, nb_chips=10): # noise file?
    chips = [dict(channels=[], register=None)
             for index in range(nb_chips)]
    module = {}
    with open(fname, 'rt') as fobj:
        module['dacs'] = dacs = []
        for dac_idx in range(nb_dacs):
            name, value = fobj.readline().split()
            dacs.append(int(value))
        module['chips'] = chips = []
        for chip_idx in range(nb_chips):
            name, value = fobj.readline().split()
            assert name == 'outBuffEnable'
            chip_register = int(value)
            channels = []
            for channel_idx in range(nb_channels):
                trim, compen, anen, calen, outcomp, counts = map(int, fobj.readline().split())
                register = (trim & 0x3F) | (compen << 9) | (anen << 8) | \
                           (calen << 7) | (outcomp << 10) | (counts << 11)
                channels.append(register)
            chips.append(dict(register=chip_register, channels=channels))
    return module


def load_settings(basefname, module_serial_numbers, nb_dacs=6, nb_channels=128, nb_chips=10):
    return [load_module_settings(basefname + '.' + serial_number, nb_dacs, nb_channels, nb_chips)
            for serial_number in module_serial_numbers]


def load_angular_conversion(fname):
    result = {}
    with open(fname, 'rt') as fobj:
        for line in fobj:
            fields = line.split()
            mod = dict(module=int(fields[1]),
                       center=float(fields[3]), ecenter=float(fields[5]),
                       conversion=float(fields[7]), econversion=float(fields[9]),
                       offset=float(fields[11]), eoffset=float(fields[13]))
            result[mod['module']] = mod
    return result


if __name__ == '__main__':
    conn = Connection(('localhost', DEFAULT_CTRL_PORT))
