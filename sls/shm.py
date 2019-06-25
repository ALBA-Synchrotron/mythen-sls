import struct
import ctype
from ctypes import Structure, c_int, c_int64, c_char, c_double

import sysv_ipc

SLS_SHM_KEY = 5678

MAX_STR_LENGTH = 1000
MAX_BADCHANS = 20000
MAX_MODS = 24
MAX_POS = 50
MAX_ROIS = 100
MAX_TIMERS = 11
MAX_ACTIONS = 8
MAX_SCAN_LEVELS = 2
MAX_SCAN_STEPS = 2000
MAX_DET = 100
c_string = c_char * MAX_STR_LENGTH
c_steps = c_double * MAX_SCAN_STEPS


class ROI(Structure):
  _fields_ = [
    ("xmin", c_int),
    ("xmax", c_int),
    ("ymin", c_int),
    ("ymax", c_int),
  ]

class AngleConversionConstant(Structure):
  _fields_ = [
    ("center", c_double),
    ("ecenter", c_double),
    ("r_conversion", c_double),
    ("er_conversion", c_double),
    ("offset", c_double),
    ("eoffset", c_double),
    ("tilt", c_double),
    ("etilt", c_double),
  ]


class SharedSlsDetector(Structure):
  _fields_ = [
    ("alreadyExisting", c_int),
    ("lastPID", c_int),
    # online flag - is set if the detector is connected, unset if socket connection is not possible
    ("onlineFlag", c_int),

    # stopped flag - is set if an acquisition error occurs or the detector is stopped manually. Is reset to 0 at the start of the acquisition
    ("stoppedFlag", c_int),

    # is the hostname (or IP address) of the detector. needs to be set before startin the communication
    ("hostname", c_string),

    # is the port used for control functions normally it should not be changed*/
    ("controlPort", c_int),
    # is the port used to stop the acquisition normally it should not be changed*/
    ("stopPort", c_int),

    # detector type  \ see :: detectorType*/
    ("myDetectorType", c_int),

    # path of the trimbits/settings files
    ("settingsDir", c_string),
    # path of the calibration files
    ("calDir", c_string),
    # number of energies at which the detector has been trimmed (unused)
    ("nTrimEn", c_int),
    # list of the energies at which the detector has been trimmed (unused)
    ("trimEnergies", c_int * 100),


    # indicator for the acquisition progress - set to 0 at the beginning of the acquisition and incremented every time that the data are written to file
    ("progressIndex", c_int),
    # total number of frames to be acquired
    ("totalProgress", c_int),

    # path of the output files
    ("filePath", c_string),

    # size of the detector

    # number of installed modules of the detector (x and y directions)
    ("nMod", c_int * 2),
    #  number of modules ( nMod[X]*nMod[Y]) \see nMod
    ("nMods", c_int),
    # maximum number of modules of the detector (x and y directions)
    ("nModMax", c_int * 2),
    #  maximum number of modules (nModMax[X]*nModMax[Y]) \see nModMax
    ("nModsMax", c_int),
    #  number of channels per chip
    ("nChans", c_int),
    #  number of channels per chip in one direction
    ("nChan", c_int * 2),
    #  number of chips per module*/
    ("nChips", c_int),
    #  number of chips per module in one direction
    ("nChip", c_int * 2),
    #  number of dacs per module*/
    ("nDacs", c_int),
    # number of adcs per module
    ("nAdcs", c_int),
    # dynamic range of the detector data
    ("dynamicRange", c_int),
    #  size of the data that are transfered from the detector
    ("dataBytes", c_int),

    # corrections  to be applied to the data \see ::correctionFlags
    ("correctionMask", c_int),
    # threaded processing flag (i.e. if data are processed and written to file in a separate thread)
    ("threadedProcessing", c_int),
    # dead time (in ns) for rate corrections
    ("tDead", c_double),
    # directory where the flat field files are stored
    ("flatFieldDir", c_string),
    # file used for flat field corrections
    ("flatFieldFile", c_string),
    # number of bad channels from bad channel list
    ("nBadChans", c_int),
    # file with the bad channels
    ("badChanFile", c_string),
    # list of bad channels
    ("badChansList", c_int * MAX_BADCHANS),
    # number of bad channels from flat field i.e. channels which read 0 in the flat field file
    ("nBadFF", c_int),
    # list of bad channels from flat field i.e. channels which read 0 in the flat field file
    ("badFFList", c_int * MAX_BADCHANS),

    # file with the angular conversion factors
    ("angConvFile", c_string),
    # array of angular conversion constants for each module \see ::angleConversionConstant
    ("angOff",  AngleConversionConstant * MAX_MODS),
    # angular direction (1 if it corresponds to the encoder direction i.e. channel 0 is 0, maxchan is positive high angle, 0 otherwise
    ("angDirection", c_int),
    # beamline fine offset (of the order of mdeg, might be adjusted for each measurements)
    ("fineOffset", c_double),
    # beamline offset (might be a few degrees beacuse of encoder offset - normally it is kept fixed for a long period of time)
    ("globalOffset", c_double),
    # number of positions at which the detector should acquire
    ("numberOfPositions", c_int),
    # list of encoder positions at which the detector should acquire
    ("detPositions", c_double * MAX_POS),
    # bin size for data merging
    ("binSize", c_double),
    # add encoder value flag (i.e. wether the detector is moving - 1 - or stationary - 0)
    ("moveFlag", c_int),


    # infos necessary for the readout to determine the size of the data

    # number of rois defined
    ("nROI", c_int),
    # list of rois
    ("roiLimits", ROI * MAX_ROIS),

    # readout flags
    ("roFlags", c_int),


    # detector setup - not needed
    # name root of the output files
    ("settingsFile", c_string),
    # detector settings (standard, fast, etc.)
    ("currentSettings", c_int),
    # detector threshold (eV)
    ("currentThresholdEV", c_int),
    # timer values
    ("timerValue", c_int64 * MAX_TIMERS),
    # clock divider
    ##("clkDiv", c_int),


    # Scans and scripts

    ("actionMask", c_int),

    ("actionScript", c_string * MAX_ACTIONS),

    ("actionParameter", c_string * MAX_ACTIONS),


    ("scanMode", c_int * MAX_SCAN_LEVELS),
    ("scanScript", c_string * MAX_SCAN_LEVELS),
    ("scanParameter", c_string * MAX_SCAN_LEVELS),
    ("nScanSteps", c_int * MAX_SCAN_LEVELS),
    ("scanSteps", c_steps * MAX_SCAN_LEVELS),
    ("scanPrecision", c_int * MAX_SCAN_LEVELS),

    #offsets*/
    # memory offsets for the flat field coefficients
    ("ffoff", c_int),
    # memory offsets for the flat filed coefficient errors
    ("fferroff", c_int),
    # memory offsets for the module structures
    ("modoff", c_int),
    # memory offsets for the dac arrays
    ("dacoff", c_int),
    # memory offsets for the adc arrays
    ("adcoff", c_int),
    # memory offsets for the chip register arrays
    ("chipoff", c_int),
    # memory offsets for the channel register arrays  -trimbits*/
    ("chanoff", c_int),

    # receiver*/
    # ip address/hostname of the receiver for the client to connect to**/
    ("receiver_hostname", c_string),
    # is the port used to communicate between client and the receiver*/
    ("receiverTCPPort", c_int),
    # is the port used to communicate between detector and the receiver*/
    ("receiverUDPPort", c_int),
    # ip address of the receiver for the detector to send packets to**/
    ("receiverUDPIP", c_string),
    # mac address of receiver for the detector to send packets to **/
    ("receiverUDPMAC", c_string),
    #  mac address of the detector **/
    ("detectorMAC", c_string),
    #  ip address of the detector **/
    ("detectorIP", c_string),
    # online flag - is set if the receiver is connected, unset if socket connection is not possible
    ("receiverOnlineFlag", c_int)
  ]


def Shm(detector_id=1):
  import sysv_ipc
  mem = sysv_ipc.SharedMemory(SLS_SHM_KEY + detector_id)
  return mem

def fill_struct(shared_sls_detector, buff):
  struct_size = ctypes.sizeof(shared_sls_detector)
  buff_size = len(buff)
  size = min(struct_size, buff_size)
  ctypes.memmove(ctypes.byref(shared_sls_detector), buff, size)

def shm_to_struct(shared_sls_detector, shm):
  struct_size = ctypes.sizeof(shared_sls_detector)
  shm_size = shm.size
  size = min(struct_size, shm_size)
  buff = shm.read(size)
  fill_struct(shared_sls_detector, buff)
