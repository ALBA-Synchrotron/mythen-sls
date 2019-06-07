import enum
import socket
import struct
import logging
import functools

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


DetectorSettings = enum.IntEnum('DetectorSettings', start=-1, names=[
  'GET_SETTINGS',
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

DetectorType = enum.IntEnum('DetectorType', start=-1, names=[
  'GET_DETECTOR_TYPE',
  'GENERIC',
  'MYTHEN',
  'PILATUS',
  'EIGER',
  'GOTTHARD',
  'PICASSO',
  'AGIPD',
  'MOENCH'
])

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

    def request_reply(self, request, reply='<i'):
        self.write(request)
        result = self.read_result()
        if result == ResultType.FAIL:
            err_msg = self.recv(1024)
            return result, err_msg.decode()
        reply = self.read_format(reply)
        return result, reply
        if result == ResultType.FORCE_UPDATE and update:
            self.update_client()
        return reply


class Detector:

    def auto_connect(f):
        name = f.__name__
        is_update = name != 'update_client'
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            with self.conn:
                result, reply = f(self, *args, **kwargs)
                if result == ResultType.FAIL:
                    raise DetectorError('{}'.format(err, err_msg.decode()))
                elif result == ResultType.FORCE_UPDATE and not is_update:
                    self.update_client()
                return reply
        return wrapper

    def __init__(self, addr):
        self.conn = Connection(addr)

    @auto_connect
    def update_client(self):
        return update_client(self.conn)

    @auto_connect
    def get_id(self, mode, mod_nb=-1):
        return get_id(self.conn, mode, mod_nb=mod_nb)

    @auto_connect
    def get_energy_threshold(self, mod_nb=0):
        return get_energy_threshold(self.conn, mod_nb)



def update_client(conn):
    request = struct.pack('<i', CommandCode.UPDATE_CLIENT)
    result, reply = conn.request_reply(request, reply='<16siiiiiiqqqqqqq')
    info =dict(last_client_ip=reply[0].strip('\x00'),
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
    pass

def get_id(conn, mode, mod_nb=-1):
    assert isinstance(mode, IdParam)
    request = struct.pack('<ii', CommandCode.GET_ID, mode)
    result, reply = conn.request_reply(request, reply='<q')
    return result, reply[0]


def get_settings(conn, mod_nb):
    request = struct.pack('<iii', CommandCode.SET_SETTINGS, DetectorSettings.GET_SETTINGS, mod_nb)
    result, reply = conn.request_reply(request, reply='<i')
    return result, DetectorSettings(reply[0])

def set_settings(conn, settings, mod_nb):
    raise NotImplementedError


def get_energy_threshold(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_THRESHOLD_ENERGY, mod_nb)
    result, reply = conn.request_reply(request, reply='<i')
    return result, reply[0]

def set_energy_threshold(conn, mod_nb, energy, settings):
    request = struct.pack('<iiii', CommandCode.SET_THRESHOLD_ENERGY, energy, mod_nb, settings)
    result, reply = conn.request_reply(request, reply='<i')
    return result, reply[0]


if __name__ == '__main__':
    conn = Connection(('bl04mythen', 1952))
