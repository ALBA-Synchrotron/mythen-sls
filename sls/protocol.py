import sys
import struct

PY36 = sys.version_info[:2] >= (3, 6)

if PY36:
    import enum
else:
    from sls import enum36 as enum

import numpy


DEFAULT_CTRL_PORT = 1952
DEFAULT_STOP_PORT = 1953

INET_ADDRSTRLEN = 16
INET_TEMPLATE = '{{:\x00<{}}}'.format(INET_ADDRSTRLEN)

GET_CODE = -1


def add_enum_to_from_string(enum, emap):
    emap_inv = {v:k for k, v in emap.items()}
    enum.string_map = emap
    enum.to_string = lambda o: emap[o]
    enum.from_string = staticmethod(lambda s: emap_inv[s.lower()])
    return enum


CommandCode = enum.IntEnum('CommandCode', start=0, names=[
    'EXEC_COMMAND',
    'GET_ERROR',

    # configuration  functions
    'DETECTOR_TYPE',
    'NB_MODULES',
    'GET_MAX_NUMBER_OF_MODULES',
    'EXTERNAL_SIGNAL',
    'EXTERNAL_COMMUNICATION_MODE',

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

    'SETTINGS',
    'GET_ENERGY_THRESHOLD',
    'SET_ENERGY_THRESHOLD',

    # Acquisition functions
    'START_ACQUISITION',
    'STOP_ACQUISITION',
    'START_READOUT',
    'RUN_STATUS',
    'START_AND_READ_ALL',
    'READ_FRAME',
    'READ_ALL',

    # Acquisition setup functions
    'TIMER',
    'TIME_LEFT',

    'DYNAMIC_RANGE',
    'READOUT_FLAGS',
    'SET_ROI',

    'SPEED',

    # Trimming
    'EXECUTE_TRIMMING',

    'EXIT_SERVER',
    'LOCK_SERVER',
    'LAST_CLIENT_IP',

    'SET_PORT',

    'UPDATE_CLIENT',

    'CONFIGURE_MAC',

    'LOAD_IMAGE',

    # multi detector structures

    'MASTER_MODE',
    'SYNCHRONIZATION_MODE',
    'READ_COUNTER_BLOCK',
    'RESET_COUNTER_BLOCK',
])


class SLSError(Exception):
    pass


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
    'NB_FRAMES',           # number of real time frames: total number of
                           # acquisitions is number or frames*number of cycles
    'ACQUISITION_TIME',    # exposure time
    'FRAME_PERIOD',        # period between exposures
    'DELAY_AFTER_TRIGGER', # delay between trigger and start of exposure or
                           # readout (in triggered mode)
    'NB_GATES',            # number of gates per frame (in gated mode)
    'NB_PROBES',           # number of probe types in pump-probe mode
    'NB_CYCLES',           # number of cycles: total number of acquisitions
                           # is number or frames*number of cycles
    'ACTUAL_TIME',         # Actual time of the detector's internal timer
    'MEASUREMENT_TIME',    # Time of the measurement from the detector (fifo)
    'PROGRESS',            # fraction of measurement elapsed - only get!
])


SpeedType = enum.IntEnum('SpeedType', start=0, names=[
    'CLOCK_DIVIDER',
    'WAIT_STATES',
    'TOT_CLOCK_DIVIDER',
    'TOT_DUTY_CYCLE',
    'SIGNAL_LENGTH'
])


RunStatus = enum.IntEnum('RunStatus', start=0, names=[
    'IDLE',         # detector ready to start acquisition - no data in memory
    'ERROR',        # error i.e. normally fifo full
    'WAITING',      # waiting for trigger or gate signal
    'FINISHED',     # acquisition not running but data in memory
    'TRANSMITTING', # acquisition running and data in memory
    'RUNNING'       # acquisition  running, no data in memory
])

RunStatus.to_string = lambda o: o.name.lower()
RunStatus.from_string = lambda s: RunStatus[s.upper()]


MasterMode = enum.IntEnum('MasterMode', start=0, names=[
    'NO_MASTER',
    'IS_MASTER',
    'IS_SLAVE'
])


SynchronizationMode = enum.IntEnum('SynchronizationMode', start=0, names=[
    'NONE',
    'MASTER_GATES',
    'MASTER_TRIGGERS',
    'SLAVE_STARTS_WHEN_MASTER_STOPS'
])


Dimension = enum.IntEnum('Dimension', start=0, names=[
    'X',
    'Y'
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


ExternalCommunicationMode = enum.IntEnum('ExternalCommunicationMode', start=0, names=[
    'AUTO_TIMING',              # internal timing
    'TRIGGER_EXPOSURE',         # trigger mode i.e. exposure is triggered
    'TRIGGER_FRAME',            # each trigger triggers one frame at a time
    'TRIGGER_READOUT',          # stop trigger mode i.e. readout is triggered by external signal
    'GATE_FIX_NUMBER',          # gated and reads out after a fixed number of gates
    'GATE_WITH_START_TRIGGER',  # gated with start trigger
    'TRIGGER_WINDOW'            # exposure time coincides with the external signal
])
add_enum_to_from_string(ExternalCommunicationMode, {
        ExternalCommunicationMode.AUTO_TIMING: 'auto',
        ExternalCommunicationMode.TRIGGER_EXPOSURE: 'trigger',
        ExternalCommunicationMode.TRIGGER_FRAME: 'trigger_frame',
        ExternalCommunicationMode.TRIGGER_READOUT: 'ro_trigger',
        ExternalCommunicationMode.GATE_FIX_NUMBER: 'gating',
        ExternalCommunicationMode.GATE_WITH_START_TRIGGER: 'triggered_gating',
        ExternalCommunicationMode.TRIGGER_WINDOW: 'trigger_window'
})


ExternalSignal = enum.IntEnum('ExternalSignal', start=0, names=[
    'OFF',                          # signal unused - tristate
    'GATE_IN_ACTIVE_HIGH',          # input gate active high
    'GATE_IN_ACTIVE_LOW',           # input gate active low
    'TRIGGER_IN_RISING_EDGE',       # input exposure trigger on rising edge
    'TRIGGER_IN_FALLING_EDGE',      # input exposure trigger on falling edge
    'RO_TRIGGER_IN_RISING_EDGE',    # input raedout trigger on rising edge
    'RO_TRIGGER_IN_FALLING_EDGE',   # input readout trigger on falling edge
    'GATE_OUT_ACTIVE_HIGH',         # output active high when detector is exposing
    'GATE_OUT_ACTIVE_LOW',          # output active low when detector is exposing
    'TRIGGER_OUT_RISING_EDGE',      # output trigger rising edge at start of exposure
    'TRIGGER_OUT_FALLING_EDGE',     # output trigger falling edge at start of exposure
    'RO_TRIGGER_OUT_RISING_EDGE',   # output trigger rising edge at start of readout
    'RO_TRIGGER_OUT_FALLING_EDGE',  # output trigger falling edge at start of readout
    'OUTPUT_LOW',                   # output always low
    'OUTPUT_HIGH',                  # output always high
    'MASTER_SLAVE_SYNCHRONIZATION'  # reserved for master/slave synchronization
                                    # in multi detector systems
])

def read_format(conn, fmt):
    n = struct.calcsize(fmt)
    reply = conn.read(n)
    if not reply:
        raise ConnectionError('connection closed')
    return struct.unpack(fmt, reply)


def read_i32(conn):
    return read_format(conn, '<i')[0]


def read_i64(conn):
    return read_format(conn, '<q')[0]


def read_result(conn):
    return ResultType(read_i32(conn))


def read_command(conn):
    return CommandCode(read_i32(conn))


def read_message(conn):
    message = conn.recv(1024).decode()
    return message.strip('\x00\n')


def _to_numpy_meta(nb_bytes, dynamic_range):
    if dynamic_range in (24, 32): # 24/32 bits
        return (nb_bytes // 4,), '<i4'
    elif dynamic_range == 16:
        return (nb_bytes // 2,), '<i2'
    elif dynamic_range == 8:
        return (nb_bytes,), '<i'
    else:
        raise ValueError('unsupported dynamic range {!r}'.format(dynamic_range))


def read_data(conn, size, dynamic_range):
    data = conn.read(size)
    data_size = len(data)
    if data_size != size:
        raise SLSError('wrong data size received: ' \
                       'expected {} bytes but got {} bytes'
                       .format(size, data_size))
    shape, dtype = _to_numpy_meta(size, dynamic_range)
    return numpy.frombuffer(data, dtype=dtype)


def request_reply(conn, request, reply_fmt='<i'):
    conn.write(request)
    result = read_result(conn)
    if result == ResultType.FAIL:
        raise SLSError(read_message(conn))
    reply = read_format(conn, reply_fmt) if reply_fmt else None
    return result, reply


def decode_update_client(reply):
    return dict(last_client_ip=reply[0].strip(b'\x00').decode(),
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


def update_client(conn):
    request = struct.pack('<i', CommandCode.UPDATE_CLIENT)
    result, reply = request_reply(conn, request, reply_fmt='<16siiiiiiqqqqqqq')
    return result, decode_update_client(reply)
    return result, info


def get_last_client_ip(conn):
    request = struct.pack('<i', CommandCode.LAST_CLIENT_IP)
    result, reply = request_reply(conn, request, reply_fmt='<16s')
    return result, reply[0].strip(b'\x00').decode()


def get_detector_type(conn):
    request = struct.pack('<i', CommandCode.DETECTOR_TYPE)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, DetectorType(reply[0])


def get_module(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_MODULE, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<iiiiiii')
    info = dict(module_nb=reply[0],
                serial_nb=reply[1],
                nb_channels=reply[2],
                nb_chips=reply[3],
                nb_dacs=reply[4],
                nb_adcs=reply[5],
                register=reply[6])
    if info['nb_dacs']:
        info['dacs'] = read_format(conn, '<{}i'.format(info['nb_dacs']))
    else:
        info['dacs'] = None
    if info['nb_adcs']:
        info['adcs'] = read_format(conn, '<{}i'.format(info['nb_adcs']))
    else:
        info['adcs'] = None
    if info['nb_chips']:
        fmt = '<{}i'.format(info['nb_chips'])
        info['chip_registers'] = read_format(conn, fmt)
    else:
        info['chip_registers'] = []
    if info['nb_channels']:
        fmt = '<{}i'.format(info['nb_channels'])
        info['channel_registers'] = read_format(conn, fmt)
    else:
        info['channel_registers'] = []
    info['gain'], info['offset'] = read_format(conn, '<dd')
    return result, info


def set_module(conn, mod_info):
    """
    mod_info: a dict with:
    - module_nb: (int) module number
    - serial_number: (int) module serial number (not important because not taken into account)
    - reg: settings level string ('standard', 'fast', etc)
    - dacs: (list[int]) of dac values (optional if there are no DACs)
    - adcs: (list[int]) of adc values (optional if there are no ADCs)
    - chips: (list[int] of dict:
      - register: (int) chip register
      - channels: (list[int]) channel values
    - gain: (double) gain as float
    - offset: (double) offset
    """
    serial_number = mod_info['serial_number']
    if isinstance(serial_number, str):
        serial_number = int(serial_number, 16)
    reg = mod_info['reg']
    if isinstance(reg, str):
        reg = DetectorSettings[reg.upper()]
    chips = mod_info['chips']
    dacs = mod_info.get('dacs', [])
    adcs = mod_info.get('adcs', [])
    channels = [channel for chip in chips for channel in chip['channels']]
    assert len(channels) == 128*10
    chip_registers = [chip['register'] for chip in chips]
    values = [
        CommandCode.SET_MODULE, mod_info['module_nb'], serial_number,
        len(channels), len(chips), len(dacs), len(adcs), reg,
        # the following 4 values are just fill garbage to match the
        # C struct sls_detector_module structure on the server. We try to fill
        # exactly the same data as official sls detector library to avoid problems
        dacs[0] if dacs else 0,
        adcs[0] if adcs else 0,
        chips[0]['register'],
        channels[0]
    ]
    values += dacs + adcs + chip_registers + channels
    assert len(values) == 1+7+4+6+0+10+128*10
    fmt = '<{}idd'.format(len(values))
    values += [mod_info['gain'], mod_info['offset']]
    request = struct.pack(fmt, *values)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]


def get_id(conn, mode, mod_nb=None):
    assert isinstance(mode, IdParam)
    if mode == IdParam.MODULE_SERIAL_NUMBER:
        assert mod_nb is not None
        request = struct.pack('<iii', CommandCode.GET_ID, mode, mod_nb)
    else:
        request = struct.pack('<ii', CommandCode.GET_ID, mode)
    result, reply = request_reply(conn, request, reply_fmt='<q')
    return result, reply[0]


def _settings(conn, mod_nb=0, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, DetectorSettings)
    request = struct.pack('<iii', CommandCode.SETTINGS, value, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, DetectorSettings(reply[0])

def get_settings(conn, mod_nb=0):
    return _settings(conn, mod_nb)

def set_settings(conn, mod_nb, value):
    return _settings(conn, mod_nb, value)


def get_energy_threshold(conn, mod_nb):
    # mod_nb = -1 means ALL
    request = struct.pack('<ii', CommandCode.GET_ENERGY_THRESHOLD, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def set_energy_threshold(conn, mod_nb, energy):
    # mod_nb = -1 means ALL
    request = struct.pack('<iiii', CommandCode.SET_ENERGY_THRESHOLD, energy,
                          mod_nb, -1)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]


def get_time_left(conn, timer):
    assert isinstance(timer, TimerType)
    request = struct.pack('<ii', CommandCode.TIME_LEFT, timer)
    result, reply = request_reply(conn, request, reply_fmt='<q')
    value = reply[0]
    if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                 TimerType.DELAY_AFTER_TRIGGER, TimerType.ACTUAL_TIME,
                 TimerType.MEASUREMENT_TIME):
        value *= 1E-9
    return result, value


def _timer(conn, timer, value=GET_CODE):
    assert isinstance(timer, TimerType)
    if value != GET_CODE:
        if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                     TimerType.DELAY_AFTER_TRIGGER):
            value *= 1E+9
        value = int(value)
    request = struct.pack('<iiq', CommandCode.TIMER, timer, value)
    result, reply = request_reply(conn, request, reply_fmt='<q')
    value = reply[0]
    if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                 TimerType.DELAY_AFTER_TRIGGER):
        value *= 1E-9
    return result, value

def get_timer(conn, timer):
    return _timer(conn, timer)

def set_timer(conn, timer, value):
    return _timer(conn, timer, value)


def _speed(conn, speed, value=GET_CODE):
    assert isinstance(speed, SpeedType)
    request = struct.pack('<iii', CommandCode.SPEED, speed, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def get_speed(conn, speed):
    return _speed(conn, speed)

def set_speed(conn, speed, value):
    return _speed(conn, speed, value)


def _dynamic_range(conn, value=GET_CODE):
    request = struct.pack('<ii', CommandCode.DYNAMIC_RANGE, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def get_dynamic_range(conn):
    return _dynamic_range(conn)

def set_dynamic_range(conn, value):
    return _dynamic_range(conn, value)


def _lock_server(conn, value=GET_CODE):
    request = struct.pack('<ii', CommandCode.LOCK_SERVER, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def get_lock_server(conn):
    return _lock_server(conn)

def set_lock_server(conn, value):
    return _lock_server(conn, value)


def _external_communication_mode(conn, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, ExternalCommunicationMode)
    request = struct.pack('<ii', CommandCode.EXTERNAL_COMMUNICATION_MODE, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, ExternalCommunicationMode(reply[0])

def get_external_communication_mode(conn):
    return _external_communication_mode(conn)

def set_external_communication_mode(conn, value):
    return _external_communication_mode(conn, value)


def _external_signal(conn, index, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, ExternalSignal)
    request = struct.pack('<iii', CommandCode.EXTERNAL_SIGNAL, index, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, ExternalSignal(reply[0])

def get_external_signal(conn, index):
    return _external_signal(conn, index)

def set_external_signal(conn, index, value):
    return _external_signal(conn, index, value)


def _synchronization_mode(conn, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, SynchronizationMode)
    request = struct.pack('<ii', CommandCode.SYNCHRONIZATION_MODE, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, SynchronizationMode(reply[0])

def get_synchronization_mode(conn):
    return _synchronization_mode(conn)

def set_synchronization_mode(conn, value):
    return _synchronization_mode(conn, value)


def _nb_modules(conn, value=GET_CODE, dimension=Dimension.X):
    request = struct.pack('<iii', CommandCode.NB_MODULES, dimension, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def get_nb_modules(conn, dimension=Dimension.X):
    return _nb_modules(conn, dimension=dimension)

def set_nb_modules(conn, value, dimension=Dimension.X):
    return _nb_modules(conn, value, dimension)


def _master_mode(conn, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, MasterMode)
    request = struct.pack('<ii', CommandCode.MASTER_MODE, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, MasterMode(reply[0])

def get_master_mode(conn):
    return _master_mode(conn)

def set_master_mode(conn, master):
    return _master_mode(conn, master)


def _readout(conn, value=GET_CODE):
    assert value == GET_CODE or isinstance(value, ReadoutFlag)
    request = struct.pack('<ii', CommandCode.READOUT_FLAGS, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, ReadoutFlag(reply[0])

def get_readout(conn):
    return _readout(conn)

def set_readout(conn, value):
    return _readout(conn, value)


def _lock(conn, value=GET_CODE):
    assert value == GET_CODE or value in (0, 1)
    request = struct.pack('<ii', CommandCode.READOUT_FLAGS, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def get_lock(conn):
    return _lock(conn)

def set_lock(conn, value):
    return _lock(conn, value)


def get_rois(conn):
    request = struct.pack('<ii', CommandCode.SET_ROI, GET_CODE)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    nb_rois = reply[0]
    raw_data = conn.read_format('<{}i'.format(4 * nb_rois))
    rois = []
    for i in range(nb_rois):
        roi = dict(xmin=raw_data[4*i+0], xmax=raw_data[4*i+1],
                   ymin=raw_data[4*i+2], ymax=raw_data[4*i+3])
        rois.append(roi)
    return rois


def read_all(conn, frame_size, dynamic_range):
    request = struct.pack('<i', CommandCode.READ_ALL)
    conn.write(request)
    return fetch_frames(conn, frame_size, dynamic_range)


def fetch_frame(conn, frame_size, dynamic_range):
    result = read_result(conn)
    if result == ResultType.OK:
        return result, read_data(conn, frame_size, dynamic_range)
    elif result == ResultType.FINISHED:
        return result, None
    elif result == ResultType.FAIL:
        # might fail because of acquisition error or because of stop
        raise SLSError('Failed to read frame')
    else:
        raise SLSError('Unexpected frame result')


def fetch_frames(conn, frame_size, dynamic_range):
    while True:
        result, frame = fetch_frame(conn, frame_size, dynamic_range)
        if result == ResultType.OK:
            yield frame
        else:
            break


def read_frame(conn, frame_size, dynamic_range):
    request = struct.pack('<i', CommandCode.READ_FRAME)
    conn.write(request)
    return read_data(conn, frame_size, dynamic_range)


def start_acquisition_and_read_all(conn):
    request = struct.pack('<i', CommandCode.START_AND_READ_ALL)
    conn.write(request)


def start_acquisition(conn, keep_connection=True):
    if keep_connection:
        return start_acquisition_and_read_all(conn)
    else:
        request = struct.pack('<i', CommandCode.START_ACQUISITION)
        return request_reply(conn, request, reply_fmt=None)




# STOP Connection -------------------------------------------------------------


def get_run_status(stop_conn):
    request = struct.pack('<i', CommandCode.RUN_STATUS)
    result, reply = request_reply(stop_conn, request, reply_fmt='<i')
    return result, RunStatus(reply[0])


def stop_acquisition(stop_conn):
    request = struct.pack('<i', CommandCode.STOP_ACQUISITION)
    return request_reply(stop_conn, request, reply_fmt=None)
