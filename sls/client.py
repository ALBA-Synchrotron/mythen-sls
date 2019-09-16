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
                       IdParam, Dimension, TimerType, SpeedType, ResultType)


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
    wrapper.wrapped = True
    return wrapper


def auto_stop_connect(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self.conn_stop:
            result, reply = f(self, *args, **kwargs)
            return reply
    return wrapper


class auto_property(property):

    wrapper = None

    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        if fget is not None and not getattr(fget, 'wrapped', False):
            fget = self.wrapper(fget)
        if fset is not None and not getattr(fset, 'wrapped', False):
            fset = self.wrapper(fset)
        super().__init__(fget, fset, fdel, doc)


class ctrl_property(auto_property):

    def wrapper(self, f):
        return auto_ctrl_connect(f)


class stop_property(auto_property):

    def wrapper(self, f):
        return auto_stop_connect(f)


class Detector:

    def __init__(self, host,
                 ctrl_port=DEFAULT_CTRL_PORT,
                 stop_port=DEFAULT_STOP_PORT):
        self.conn_ctrl = Connection((host, ctrl_port))
        self.conn_stop = Connection((host, stop_port))

    @auto_ctrl_connect
    def update_client(self):
        return protocol.update_client(self.conn_ctrl)

    @auto_ctrl_connect
    def get_nb_modules(self, dimension=Dimension.X):
        return protocol.get_nb_modules(self.conn_ctrl, dimension)

    @auto_ctrl_connect
    def set_nb_modules(self, n, dimension=Dimension.X):
        return protocol.set_nb_modules(self.conn_ctrl, n, dimension)

    @auto_ctrl_connect
    def get_id(self, mode, mod_nb=None):
        return protocol.get_id(self.conn_ctrl, mode, mod_nb=mod_nb)

    def get_module_serial_number(self, mod_nb):
        return self.get_id(IdParam.MODULE_SERIAL_NUMBER, mod_nb)

    @auto_ctrl_connect
    def get_external_signal(self, index):
        return protocol.get_external_signal(self.conn_ctrl, index)

    @auto_ctrl_connect
    def set_external_signal(self, index, value):
        return protocol.set_external_signal(self.conn_ctrl, index, value)

    @property
    def firmware_version(self):
        return self.get_id(IdParam.DETECTOR_FIRMWARE_VERSION)

    @property
    def serial_number(self):
        return self.get_id(IdParam.DETECTOR_SERIAL_NUMBER)

    @property
    def software_version(self):
        return self.get_id(IdParam.DETECTOR_SOFTWARE_VERSION)

    @property
    def module_firmware_version(self):
        return self.get_id(IdParam.MODULE_FIRMWARE_VERSION)

    @auto_ctrl_connect
    def get_energy_threshold(self, mod_nb):
        return protocol.get_energy_threshold(self.conn_ctrl, mod_nb)

    @auto_ctrl_connect
    def set_energy_threshold(self, mod_nb, energy):
        return protocol.set_energy_threshold(self.conn_ctrl, mod_nb, energy)

    @property
    def energy_threshold(self):
        return self.get_energy_threshold(-1)

    @energy_threshold.setter
    def energy_threshold(self, energy):
        self.set_energy_threshold(-1, energy)

    @ctrl_property
    def lock(self):
        return protocol.get_lock(self.conn_ctrl)

    @lock.setter
    def lock(self, value):
        return protocol.set_lock(self.conn_ctrl, 1 if value else 0)

    @ctrl_property
    def synchronization_mode(self):
        return protocol.get_synchronization_mode(self.conn_ctrl)

    @synchronization_mode.setter
    def synchronization_mode(self, value):
        return protocol.set_synchronization_mode(self.conn_ctrl, value)

    @ctrl_property
    def timing_mode(self):
        return protocol.get_external_communication_mode(self.conn_ctrl)

    @timing_mode.setter
    def timing_mode(self, value):
        return protocol.set_external_communication_mode(self.conn_ctrl, value)

    external_communication_mode = timing_mode

    @ctrl_property
    def detector_type(self):
        return protocol.get_detector_type(self.conn_ctrl)

    @auto_ctrl_connect
    def get_module(self, mod_nb):
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

    @ctrl_property
    def master_mode(self):
        return protocol.get_master_mode(self.conn_ctrl)

    @master_mode.setter
    def master_mode(self, master_mode):
        return protocol.set_master_mode(self.conn_ctrl, master_mode)

    @ctrl_property
    def dynamic_range(self):
        return protocol.get_dynamic_range(self.conn_ctrl)

    @dynamic_range.setter
    def dynamic_range(self, dynamic_range):
        return protocol.set_dynamic_range(self.conn_ctrl, dynamic_range)

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

    @stop_property
    def run_status(self):
        return protocol.get_run_status(self.conn_stop)

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

    @ctrl_property
    def readout(self):
        return protocol.get_readout(self.conn_ctrl)

    @readout.setter
    def readout(self, value):
        return protocol.set_readout(self.conn_ctrl, value)

    @ctrl_property
    def rois(self):
        return protocol.get_rois(self.conn_ctrl)

    @auto_ctrl_connect
    def get_speed(self, speed_type):
        return protocol.get_speed(self.conn_ctrl, speed_type)

    @auto_ctrl_connect
    def set_speed(self, speed_type, value):
        return protocol.set_speed(self.conn_ctrl, speed_type, value)

    @property
    def clock_divider(self):
        return self.get_speed(SpeedType.CLOCK_DIVIDER)

    @clock_divider.setter
    def clock_divider(self, value):
        return self.set_speed(SpeedType.CLOCK_DIVIDER, value)

    @property
    def wait_states(self):
        return self.get_speed(SpeedType.WAIT_STATES)

    @wait_states.setter
    def wait_states(self, value):
        return self.set_speed(SpeedType.WAIT_STATES, value)

    @property
    def tot_clock_divider(self):
        return self.get_speed(SpeedType.TOT_CLOCK_DIVIDER)

    @tot_clock_divider.setter
    def tot_clock_divider(self, value):
        return self.set_speed(SpeedType.TOT_CLOCK_DIVIDER, value)

    @property
    def tot_duty_cycle(self):
        return self.get_speed(SpeedType.TOT_DUTY_CYCLE)

    @tot_duty_cycle.setter
    def tot_duty_cycle(self, value):
        return self.set_speed(SpeedType.TOT_DUTY_CYCLE, value)

    @property
    def signal_length(self):
        return self.get_speed(SpeedType.SIGNAL_LENGTH)

    @signal_length.setter
    def signal_length(self, value):
        return self.set_speed(SpeedType.SIGNAL_LENGTH, value)

    @ctrl_property
    def last_client_ip(self):
        return protocol.get_last_client_ip(self.conn_ctrl)


def _acquire(detector, exposure_time=1, nb_frames=1, nb_cycles=1):
    detector.exposure_time = exposure_time
    detector.nb_frames = nb_frames
    detector.nb_cycles = nb_cycles
    for frame in detector.acquire():
        yield frame


if __name__ == '__main__':
    conn = Connection(('localhost', DEFAULT_CTRL_PORT))
