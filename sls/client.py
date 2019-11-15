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

import select
import socket
import inspect
import logging
import functools

import numpy

from . import protocol
from .protocol import (DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT, SLSError,
                       IdParam, Dimension, TimerType, SpeedType, ResultType)


TEMPLATE = '''\
{o.detector_type.name} at tcp://{o.conn_ctrl.addr[0]}:{o.conn_ctrl.addr[1]}
Serial nb.: {o.serial_number}
Soft. version: {o.software_version}
Status: {o.run_status.name}
Dynamic range: {o.dynamic_range}
Energy threshold: {o.energy_threshold}
Exposure_time: {o.exposure_time}
Master: {o.master_mode.name}
Synchronization: {o.synchronization_mode.name}
Timing: {o.timing_mode.name}
Communication: {o.external_communication_mode.name}
Nb. frames: {o.nb_frames}
Nb. cycles: {o.nb_cycles}
Readout: {o.readout}'''


class Connection:

    def __init__(self, addr):
        self.addr = addr
        self.sock = None
        self.log = logging.getLogger('Connection({0[0]}:{0[1]})'.format(addr))

    def connect(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
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
        data = b''
        while len(data) < size:
            buff = self.reader.read(size)
            if not buff:
                self.close()
                raise ConnectionError('connection closed')
            self.log.debug('read: %r', buff)
            data += buff
        return data

    def fileno(self):
        return self.sock.fileno()


def auto_ctrl_connect(f):
    name = f.__name__
    is_update = name == 'update_client'
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        with self.conn_ctrl:
            result, reply = f(self, *args, **kwargs)
            if not is_update:
                if result == ResultType.FORCE_UPDATE or self._info is None:
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


def progress_report(detector, info):
    nb_cycles_left = detector.nb_cycles_left + 2
    nb_frames_left = detector.nb_frames_left + 2
    exposure_time_left = detector.exposure_time_left
    cycle_nb = info['nb_cycles'] - nb_cycles_left
    frame_nb = info['nb_frames'] - nb_frames_left
    exposure_time = info['acq_time'] * 1e-9 - exposure_time_left
    return dict(
        info, exposure_time_left=exposure_time_left,
        nb_cycles_left=nb_cycles_left, nb_frames_left=nb_frames_left,
        cycle_nb=cycle_nb, frame_nb=frame_nb, exposure_time=exposure_time)


class Detector:

    def __init__(self, host,
                 ctrl_port=DEFAULT_CTRL_PORT,
                 stop_port=DEFAULT_STOP_PORT):
        self._info = None
        self.host = host
        self.conn_ctrl = Connection((host, ctrl_port))
        self.conn_stop = Connection((host, stop_port))

    @auto_ctrl_connect
    def update_client(self):
        result = protocol.update_client(self.conn_ctrl)
        self._info = result[1]
        return result

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
        # detector stores 24bits dynamic range as 32. We always present
        # 24 to the user
        result = protocol.get_dynamic_range(self.conn_ctrl)
        if result == 32:
            result = 24
        return result

    @dynamic_range.setter
    def dynamic_range(self, dynamic_range):
        # detector stores 24bits dynamic range as 32. We always present
        # 24 to the user
        if dynamic_range == 24:
            dynamic_range = 32
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

    @auto_stop_connect
    def stop_acquisition(self):
        return protocol.stop_acquisition(self.conn_stop)

    @auto_ctrl_connect
    def start_acquisition(self):
        return protocol.start_acquisition(self.conn_ctrl)

    def acquire(self, update_interval=None):
        info = self.update_client()
        frame_size = info['data_bytes']
        dynamic_range = info['dynamic_range']
        with self.conn_ctrl:
            try:
                protocol.start_and_read_all(self.conn_ctrl)
                # for small acq. time don't send progress
                if update_interval is None:
                    for event in protocol.fetch_frames(self.conn_ctrl,
                                                       frame_size,
                                                       dynamic_range):
                        yield event
                else:
                    fds = self.conn_ctrl,
                    while True:
                        rfds, _, _ = select.select(fds, (), (), update_interval)
                        if rfds:
                            result, frame = self.fetch_frame(frame_size,
                                                             dynamic_range)
                            if result != ResultType.OK:
                                break
                            event = 'frame', frame
                        else:
                            event = 'progress', progress_report(self, info)
                        yield event
                    yield 'progress', progress_report(self, info)
            except BaseException as err:
                # make sure acq is stopped before closing the control socket
                # otherwise detector hangs
                self.stop_acquisition()
                raise

    def fetch_frame(self, frame_size, dynamic_range):
        return protocol.fetch_frame(self.conn_ctrl, frame_size, dynamic_range)

    @auto_ctrl_connect
    def read_all(self, frame_size, dynamic_range):
        for event in protocol.read_all(self.conn_ctrl, frame_size,
                                       dynamic_range):
            yield event

    @auto_ctrl_connect
    def read_frame(self, frame_size, dynamic_range):
        return protocol.read_frame(self.conn_ctrl, frame_size, dynamic_range)

    @ctrl_property
    def readout(self):
        return protocol.get_readout(self.conn_ctrl)

    @readout.setter
    def readout(self, value):
        return protocol.set_readout(self.conn_ctrl, value)

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

    def __repr__(self):
        return TEMPLATE.format(o=self)


def dump_state(detector):
    klass = type(detector)
    members = ((name, getattr(klass, name)) for name in dir(klass)
               if not name.startswith('_'))
    return {name:getattr(detector, name) for name, member in members
            if inspect.isdatadescriptor(member)}


def acquire(detector, exposure_time=1, nb_frames=1, nb_cycles=1, update_interval=0.25):
    exposure_time = float(exposure_time)
    detector.exposure_time = exposure_time
    detector.nb_frames = nb_frames
    detector.nb_cycles = nb_cycles
    return detector.acquire(update_interval=update_interval)


def acquisition_text(detector, exposure_time=1, nb_frames=1, nb_cycles=1, update_interval=0.25):
    templ = 'Current frame time left {{exposure_time_left:.3f}}s; ' \
            'Frame #{{frame_nb:03}}/{:03}; ' \
            'Cycle #{{cycle_nb:03}}/{:03};'.format(nb_frames, nb_cycles)
    for event_type, event in acquire(detector, exposure_time=exposure_time,
                                     nb_frames=nb_frames, nb_cycles=nb_cycles,
                                     update_interval=update_interval):
        if event_type == 'progress':
            print(templ.format(**event), end='\n', flush=True)


def acquisition_progress(detector, exposure_time=1, nb_frames=1, nb_cycles=1, update_interval=0.25):
    import tqdm
    if nb_frames == 0:
        nb_frames = 1
    if nb_cycles == 0:
        nb_cycles = 1
    exp_time_secs = int(exposure_time * 4)
    nb_steps = exp_time_secs * nb_frames * nb_cycles
    previous_step = 0
    with tqdm.tqdm(total=nb_steps) as pbar:
        for event_type, event in acquire(detector, exposure_time, nb_frames, nb_cycles, update_interval):
            if event_type == 'progress':
                frame_nb = event['frame_nb'] 
                cycle_nb = event['cycle_nb']
                curr_time = int(event['exposure_time'] * 4)
                step = min(curr_time + exp_time_secs*frame_nb + exp_time_secs*nb_frames*cycle_nb, nb_steps)
                pbar.update(step-previous_step)
                previous_step = step


if __name__ == '__main__':
    conn = Connection(('localhost', DEFAULT_CTRL_PORT))
