import enum
import struct

DEFAULT_CTRL_PORT = 1952
DEFAULT_STOP_PORT = 1953

INET_ADDRSTRLEN = 16
INET_TEMPLATE = '{{:\x00<{}}}'.format(INET_ADDRSTRLEN)

GET_CODE = -1


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
    'GET_ENERGY_THRESHOLD',
    'SET_ENERGY_THRESHOLD',

    # Acquisition functions
    'START_ACQUISITION',
    'STOP_ACQUISITION',
    'START_READOUT',
    'GET_RUN_STATUS',
    'START_AND_READ_ALL',
    'READ_FRAME',
    'READ_ALL',

    # Acquisition setup functions
    'TIMER',
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
    return conn.recv(1024).decode()


def read_data(conn, size):
    data = conn.read(size)
    data_size = len(data)
    if data_size != size:
        raise SLSError('wrong data size received: ' \
                       'expected {} bytes but got {} bytes'
                       .format(size, data_size))
    return numpy.frombuffer(data, dtype='<i4')


def request_reply(conn, request, reply_fmt='<i'):
    conn.write(request)
    result = read_result(conn)
    if result == ResultType.FAIL:
        raise SLSError(read_message(conn))
    reply = read_format(conn, reply_fmt) if reply_fmt else None
    return result, reply


def update_client(conn):
    request = struct.pack('<i', CommandCode.UPDATE_CLIENT)
    result, reply = request_reply(conn, request, reply_fmt='<16siiiiiiqqqqqqq')
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
    request = struct.pack('<i', CommandCode.GET_DETECTOR_TYPE)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, DetectorType(reply[0])


def get_module(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_MODULE, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<iiiiiii')
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


def get_id(conn, mode, mod_nb=GET_CODE):
    assert isinstance(mode, IdParam)
    request = struct.pack('<ii', CommandCode.GET_ID, mode)
    result, reply = request_reply(conn, request, reply_fmt='<q')
    return result, reply[0]


def get_settings(conn, mod_nb):
    request = struct.pack('<iii', CommandCode.SET_SETTINGS, GET_CODE, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, DetectorSettings(reply[0])


def get_energy_threshold(conn, mod_nb):
    request = struct.pack('<ii', CommandCode.GET_ENERGY_THRESHOLD, mod_nb)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]

def set_energy_threshold(conn, mod_nb, energy, settings):
    request = struct.pack('<iiii', CommandCode.SET_ENERGY_THRESHOLD, energy,
                          mod_nb, settings)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, reply[0]


def get_time_left(conn, timer):
    assert isinstance(timer, TimerType)
    request = struct.pack('<ii', CommandCode.GET_TIME_LEFT, timer)
    result, reply = request_reply(conn, request, reply_fmt='<q')
    value = reply[0]
    if timer in (TimerType.ACQUISITION_TIME, TimerType.FRAME_PERIOD,
                 TimerType.DELAY_AFTER_TRIGGER):
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


def _synchronization(conn, value=GET_CODE):
    request = struct.pack('<ii', CommandCode.SET_SYNCHRONIZATION_MODE, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, SyncronizationMode(reply[0])

def get_synchronization(conn):
    return _synchronization(conn)

def set_synchronization(conn, value):
    return _synchronization(conn, value)


def _master(conn, value=GET_CODE):
    request = struct.pack('<ii', CommandCode.SET_MASTER, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, Master(reply[0])

def get_master(conn):
    return _master(conn)

def set_master(conn, master):
    return _master(conn, master)


def _readout(conn, value=GET_CODE):
    request = struct.pack('<ii', CommandCode.SET_READOUT_FLAGS, value)
    result, reply = request_reply(conn, request, reply_fmt='<i')
    return result, ReadoutFlag(reply[0])

def get_readout(conn):
    return _readout(conn)

def set_readout(conn, value):
    return _readout(conn, value)


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


def start_acquisition(conn):
    request = struct.pack('<i', CommandCode.START_ACQUISITION)
    result, reply = request_reply(conn, request, reply_fmt=None)


def start_and_read_all(conn, frame_size):
    request = struct.pack('<i', CommandCode.START_AND_READ_ALL)
    conn.write(request)
    while True:
        try:
            result = read_result(conn)
            if result == ResultType.OK:
                frame = read_data(conn, frame_size)
                yield frame
            elif result == ResultType.FINISHED:
                raise StopIteration(read_message(conn))
            elif result == ResultType.FAIL:
                raise SLSError(read_message(conn))
        except ConnectionError:
            break


# STOP Connection -------------------------------------------------------------


def get_run_status(stop_conn):
    request = struct.pack('<i', CommandCode.GET_RUN_STATUS)
    result, reply = request_reply(stop_conn, request, reply_fmt='<i')
    return result, RunStatus(reply[0])


def stop_acquisition(stop_conn):
    request = struct.pack('<i', CommandCode.STOP_ACQUISITION)
    result, reply = request_reply(stop_conn, request, reply_fmt=None)
