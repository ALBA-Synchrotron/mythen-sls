import enum
import socket
import struct
import logging
import functools

import numpy

INET_ADDRSTRLEN = 16

CommandCode = enum.IntEnum('CommandCode', start=0, names=[
    'EXEC_COMMAND',
    'GET_ERROR',

    # configuration  functions
    'GET_DETECTOR_TYPE',
    'SET_NUMBER_OF_MODULES',
    'GET_MAX_NUMBER_OF_MODULES',
    'SET_EXTERNAL_SIGNAL_FLAG',
    'SET_EXTERNAL_COMMUNICATION_MODE',

    # Tests and identification

    'GET_ID',
    'DIGITAL_TEST',
    'ANALOG_TEST',
    'ENABLE_ANALOG_OUT',
    'CALIBRATION_PULSE',

    # Initialization functions
    'SET_DAC',
    'GET_ADC',
    'WRITE_REGISTER',
    'READ_REGISTER',
    'WRITE_MEMORY',
    'READ_MEMORY',

    'SET_CHANNEL',
    'GET_CHANNEL',
    'SET_ALL_CHANNELS',

    'SET_CHIP',
    'GET_CHIP',
    'SET_ALL_CHIPS',

    'SET_MODULE',
    'GET_MODULE',
    'SET_ALL_MODULES',

    'SET_SETTINGS',
    'GET_THRESHOLD_ENERGY',
    'SET_THRESHOLD_ENERGY',

    # Acquisition functions
    'START_ACQUISITION',
    'STOP_ACQUISITION',
    'START_READOUT',
    'GET_RUN_STATUS',
    'START_AND_READ_ALL',
    'READ_FRAME',
    'READ_ALL',

    # Acquisition setup functions
    'SET_TIMER',
    'GET_TIME_LEFT',

    'SET_DYNAMIC_RANGE',
    'SET_READOUT_FLAGS',
    'SET_ROI',

    'SET_SPEED',

    # Trimming
    'EXECUTE_TRIMMING',

    'EXIT_SERVER',
    'LOCK_SERVER',
    'GET_LAST_CLIENT_IP',

    'SET_PORT',

    'UPDATE_CLIENT',

    'CONFIGURE_MAC',

    'LOAD_IMAGE',

    # multi detector structures

    'SET_MASTER',

    'SET_SYNCHRONIZATION_MODE',

    'READ_COUNTER_BLOCK',

    'RESET_COUNTER_BLOCK',
])


class DetectorError(Exception):
    pass


CommandCode.htonl = lambda self: struct.pack('<i', self.value)


IdParam = enum.IntEnum('IdParam', start=0, names=[
    'MODULE_SERIAL_NUMBER',
    'MODULE_FIRMWARE_VERSION',
    'DETECTOR_SERIAL_NUMBER',
    'DETECTOR_FIRMWARE_VERSION',
    'DETECTOR_SOFTWARE_VERSION',
    'RECEIVER_VERSION'
])


ResultType = enum.IntEnum('ResultType', start=0, names=[
    'OK',
    'FAIL',
    'FINISHED',
    'FORCE_UPDATE'
])


DetectorSettings = enum.IntEnum('DetectorSettings', start=0, names=[
  'STANDARD',
  'FAST',
  'HIGHGAIN',
  'DYNAMICGAIN',
  'LOWGAIN',
  'MEDIUMGAIN',
  'VERYHIGHGAIN',
  'UNDEFINED',
  'UNINITIALIZED'
])

DetectorType = enum.IntEnum('DetectorType', start=0, names=[
  'GENERIC',
  'MYTHEN',
  'PILATUS',
  'EIGER',
  'GOTTHARD',
  'PICASSO',
  'AGIPD',
  'MOENCH'
])

TimerType = enum.IntEnum('TimerType', start=0, names=[
    'FRAME_NUMBER',        # number of real time frames: total number of
                           # acquisitions is number or frames*number of cycles
    'ACQUISITION_TIME',    # exposure time
    'FRAME_PERIOD',        # period between exposures
    'DELAY_AFTER_TRIGGER', # delay between trigger and start of exposure or
                           # readout (in triggered mode)
    'GATES_NUMBER',        # number of gates per frame (in gated mode)
    'PROBES_NUMBER',       # number of probe types in pump-probe mode
    'CYCLES_NUMBER',       # number of cycles: total number of acquisitions
                           # is number or frames*number of cycles
    'ACTUAL_TIME',         # Actual time of the detector's internal timer
    'MEASUREMENT_TIME',    # Time of the measurement from the detector (fifo)
    'PROGRESS',            # fraction of measurement elapsed - only get!
    'MEASUREMENTS_NUMBER'
])

RunStatus = enum.IntEnum('RunStatus', start=0, names=[
    'IDLE',         # detector ready to start acquisition - no data in memory
    'ERROR',        # error i.e. normally fifo full
    'WAITING',      # waiting for trigger or gate signal
    'RUN_FINISHED', # acquisition not running but data in memory
    'TRANSMITTING', # acquisition running and data in memory
    'RUNNING'       # acquisition  running, no data in memory
])

Master = enum.IntEnum('Master', start=0, names=[
    'NO_MASTER',
    'IS_MASTER',
    'IS_SLAVE'
])

SyncronizationMode = enum.IntEnum('SynchronizationMode', start=0, names=[
    'NO_SYNCHRONIZATION',
    'MASTER_GATES',
    'MASTER_TRIGGERS',
    'SLAVE_STARTS_WHEN_MASTER_STOPS'
])

class ReadoutFlag(enum.IntFlag):
    NORMAL_READOUT = 0x0             # 
    STORE_IN_RAM = 0x1               # data are stored in ram and sent only after end
                                     # of acquisition for faster frame rate
    READ_HITS = 0x2                  # return only the number of the channel which counted
                                     # ate least one
    ZERO_COMPRESSION = 0x4           # returned data are 0-compressed
    PUMP_PROBE_MODE = 0x8            # pump-probe mode
    BACKGROUND_CORRECTIONS = 0x1000  # background corrections
    TOT_MODE = 0x2000                # pump-probe mode
    CONTINOUS_RO = 0x4000            # pump-probe mode


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
        self.log.debug('recv: %r', data)
        return data

    def read(self, size):
        data = self.reader.read(size)
        self.log.debug('read: %r', data)
        return data

    def read_format(self, fmt):
        n = struct.calcsize(fmt)
        return struct.unpack(fmt, self.read(n))

    def read_i32(self):
        return self.read_format('<i')[0]

    def read_i64(self):
        return self.read_format('<q')[0]

    def read_result(self):
        return ResultType(self.read_i32())

    def request_reply(self, request, reply_fmt='<i'):
        self.write(request)
        result = self.read_result()
        if result == ResultType.FAIL:
            err_msg = self.recv(1024)
            raise DetectorError('{}'.format(err, err_msg.decode()))
        reply = self.read_format(reply_fmt) if reply_fmt else None
        return result, reply


class Detector:

    def auto_ctrl_connect(f):
        name = f.__name__
        is_update = name != 'update_client'
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
                if result == ResultType.FAIL:
                    raise DetectorError('{}'.format(err, err_msg.decode()))
                return reply
        return wrapper

    def __init__(self, host, ctrl_port=1952, stop_port=1953):
        self.conn_ctrl = Connection((host, ctrl_port))
        self.conn_stop = Connection((host, stop_port))

    @auto_ctrl_connect
    def update_client(self):
        return update_client(self.conn_ctrl)

    @auto_ctrl_connect
    def get_id(self, mode, mod_nb=-1):
        return get_id(self.conn_ctrl, mode, mod_nb=mod_nb)

    @auto_ctrl_connect
    def get_energy_threshold(self, mod_nb=0):
        return get_energy_threshold(self.conn_ctrl, mod_nb)

    @auto_ctrl_connect
    def get_synchronization(self):
        return get_synchronization(self.conn_ctrl)

    @auto_ctrl_connect
    def set_synchronization(self, value):
        return set_synchronization(self.conn_ctrl, value)

    synchronization = property(get_synchronization, set_synchronization)

    @auto_ctrl_connect
    def get_type(self):
        return get_detector_type(self.conn_ctrl)

    @auto_ctrl_connect
    def get_module(self, mod_nb=0):
        return get_module(self.conn_ctrl, mod_nb)

    @auto_ctrl_connect
    def get_time_left(self, timer):
        return get_time_left(self.conn_ctrl, timer)

    @property
    def exposure_time_left(self):
        return self.get_time_left(TimerType.ACQUISITION_TIME)

    @auto_ctrl_connect
    def set_timer(self, timer, value):
        return set_timer(self.conn_ctrl, timer, value)

    @auto_ctrl_connect
    def get_timer(self, timer):
        return get_timer(self.conn_ctrl, timer)

    @property
    def exposure_time(self):
        return self.get_timer(TimerType.ACQUISITION_TIME)

    @exposure_time.setter
    def exposure_time(self, exposure_time):
        self.set_timer(TimerType.ACQUISITION_TIME, exposure_time)

    @property
    def nb_frames(self):
        return self.get_timer(TimerType.FRAME_NUMBER)

    @nb_frames.setter
    def nb_frames(self, nb_frames):
        self.set_timer(TimerType.FRAME_NUMBER, nb_frames)

    @property
    def nb_cycles(self):
        return self.get_timer(TimerType.CYCLES_NUMBER)

    @nb_cycles.setter
    def nb_cycles(self, nb_cycles):
        self.set_timer(TimerType.CYCLES_NUMBER, nb_cycles)

    @auto_ctrl_connect
    def get_master(self):
        return get_master(self.conn_ctrl)

    @auto_ctrl_connect
    def set_master(self, master):
        return set_master(self.conn_ctrl, master)

    master = property(get_master, set_master)

    @auto_ctrl_connect
    def get_settings(self, mod_nb):
        return get_settings(self.conn_ctrl, mod_nb)
    
    @auto_stop_connect
    def get_run_status(self):
        return get_run_status(self.conn_stop)

    @property
    def run_status(self):
        return self.get_run_status()

    @auto_ctrl_connect
    def start_acquisition(self):
        start_acquisition(self.conn_ctrl)

    @auto_stop_connect
    def stop_acquisition(self):
        stop_acquisition(self.conn_stop)

    @auto_ctrl_connect
    def get_readout(self):
        return get_readout(self.conn_ctrl)

    @auto_ctrl_connect
    def set_readout(self, value):
        return set_readout(self.conn_ctrl, value)

    readout = property(get_readout, set_readout)

    @auto_ctrl_connect
    def get_rois(self):
        return get_rois(self.conn_ctrl)

    rois = property(get_rois)


def update_client(conn):
    request = struct.pack('<i', CommandCode.UPDATE_CLIENT)
    result, reply = conn.request_reply(request, reply_fmt='<16siiiiiiqqqqqqq')
    info = dict(last_client_ip=reply[0].strip(b'\x00').decode(),
                nb_modules=reply[1],
                dynamic_range=reply[3],
                data_bytes=reply[4],
                settings=DetectorSettings(reply[5]),
                energy_threshold=reply[6],
                nb_frames=reply[7],
                acq_time=reply[8],
                frame_period=reply[9],
                delay_after_trigger=reply[10],
                nb_gates=reply[11],
                nb_probes=reply[12],
                nb_cycles=reply[13])
    return result, info


def get_detector_type(conn):
    request = struct.pack('<ii', CommandCode.GET_DETECTOR_TYPE, -1)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, DetectorType(reply[0])


def get_module(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_MODULE, mod_nb)
    result, reply = conn.request_reply(request, reply_fmt='<iiiiiii')
    info = dict(module_nb=reply[0],
                serial_nb=reply[1],
                nb_channels=reply[2],
                nb_chips=reply[3],
                nb_dac=reply[4],
                nb_adc=reply[5],
                register=reply[6])
    if info['nb_dac']:
        info['dacs'] = conn.read_format('<{}i'.format(info['nb_dac']))
    else:
        info['dacs'] = None
    if info['nb_adc']:
        info['adcs'] = conn.read_format('<{}i'.format(info['nb_adc']))
    else:
        info['adcs'] = None
    if info['nb_chips']:
        fmt = '<{}i'.format(info['nb_chips'])
        info['chip_registers'] = conn.read_format(fmt)
    else:
        info['chip_registers'] = []
    if info['nb_channels']:
        fmt = '<{}i'.format(info['nb_channels'])
        info['channel_registers'] = conn.read_format(fmt)
    else:
        info['channel_registers'] = []
    info['gain'], info['offset'] = conn.read_format('<dd')
    return result, info
              
    
    
def get_id(conn, mode, mod_nb=-1):
    assert isinstance(mode, IdParam)
    request = struct.pack('<ii', CommandCode.GET_ID, mode)
    result, reply = conn.request_reply(request, reply_fmt='<q')
    return result, reply[0]


def get_settings(conn, mod_nb):
    request = struct.pack('<iii', CommandCode.SET_SETTINGS, -1, mod_nb)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, DetectorSettings(reply[0])


def get_energy_threshold(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_THRESHOLD_ENERGY, mod_nb)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, reply[0]

def set_energy_threshold(conn, mod_nb, energy, settings):
    request = struct.pack('<iiii', CommandCode.SET_THRESHOLD_ENERGY, energy,
                          mod_nb, settings)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, reply[0]


def get_time_left(conn, timer):
    assert isinstance(timer, TimerType)
    request = struct.pack('<ii', CommandCode.GET_TIME_LEFT, timer)
    result, reply = conn.request_reply(request, reply_fmt='<q')
    value = reply[0]
    if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                 TimerType.DELAY_AFTER_TRIGGER):
        value *= 1E-9
    return result, value


def _timer(conn, timer, value=-1):
    assert isinstance(timer, TimerType)
    if value != -1:
        if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                     TimerType.DELAY_AFTER_TRIGGER):
            value *= 1E+9
        value = int(value)
    request = struct.pack('<iiq', CommandCode.SET_TIMER, timer, value)
    result, reply = conn.request_reply(request, reply_fmt='<q')
    value = reply[0]
    if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                 TimerType.DELAY_AFTER_TRIGGER):
        value *= 1E-9
    return result, value

def get_timer(conn, timer):
    return _timer(conn, timer)

def set_timer(conn, timer, value):
    return _timer(conn, timer, value)


def _synchronization(conn, value=-1):
    request = struct.pack('<ii', CommandCode.SET_SYNCHRONIZATION_MODE, value)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, SyncronizationMode(reply[0])
    
def get_synchronization(conn):
    return _synchronization(conn)

def set_synchronization(conn, value):
    return _synchronization(conn, value)


def _master(conn, value=-1):
    request = struct.pack('<ii', CommandCode.SET_MASTER, value)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, Master(reply[0])

def get_master(conn):
    return _master(conn)

def set_master(conn, master):
    return _master(conn, master)


def _readout(conn, value=-1):
    request = struct.pack('<ii', CommandCode.SET_READOUT_FLAGS, value)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    return result, ReadoutFlag(reply[0])

def get_readout(conn):
    return _readout(conn)

def set_readout(conn, value):
    return _readout(conn, value)


def get_rois(conn):
    request = struct.pack('<ii', CommandCode.SET_ROI, -1)
    result, reply = conn.request_reply(request, reply_fmt='<i')
    nb_rois = reply[0]
    raw_data = conn.read_format('<{}i'.format(4 * nb_rois))
    rois = []
    for i in range(nb_rois):
        roi = dict(xmin=raw_data[4*i+0], xmax=raw_data[4*i+1],
                   ymin=raw_data[4*i+2], ymax=raw_data[4*i+3])
        rois.append(roi)
    return rois


def start_acquisition(conn):
    request = struct.pack('<i', CommandCode.START_ACQUISITION)
    result, reply = conn.request_reply(request, reply_fmt=None)


# STOP Connection -------------------------------------------------------------


def get_run_status(stop_conn):
    request = struct.pack('<i', CommandCode.GET_RUN_STATUS)
    result, reply = stop_conn.request_reply(request, reply_fmt='<i')
    return result, RunStatus(reply[0])


def stop_acquisition(stop_conn):
    request = struct.pack('<i', CommandCode.STOP_ACQUISITION)
    result, reply = stop_conn.request_reply(request, reply_fmt=None)


if __name__ == '__main__':
    conn = Connection(('bl04mythen', 1952))
