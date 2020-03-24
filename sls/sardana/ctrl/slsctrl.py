import queue
import threading

from sls.client import Detector
from sls.protocol import RunStatus

from sardana import State, DataAccess
from sardana.pool.controller import OneDController, Description, Access, \
    Type, Memorize, NotMemorized, MaxDimSize


class MythenSLSController(OneDController):

    gender = "Mythen"
    model = "Mythen II"
    organization = "SLS"

    MaxDevice = 1

    ctrl_properties = {
        'address': {
            Description: 'IP/host',
            Type: str
        }
    }

    ctrl_attributes = {
        'energy_threshold': {
            Description: 'Energy threshold (eV)',
            Type: float,
            Access: DataAccess.ReadWrite
        }
    }

    axis_attributes = dict(ctrl_attributes)

    StateMap = {
        RunStatus.IDLE: State.On,
        RunStatus.ERROR: State.Fault,
        RunStatus.WAITING: State.Running,   # Waiting for trigger
        RunStatus.FINISHED: State.Running,  # Data in memory so need to read it
        RunStatus.TRANSMITTING: State.Running,
        RunStatus.RUNNING: State.Running
    }

    def __init__(self, inst, props, *args, **kwargs):
        super().__init__(inst, props, *args, **kwargs)
        self.detector = Detector(self.address)
        self.acq = None

    def _stop(self):
        if self.acq:
            self.acq.stop()
            self.acq = None
            return True
        return False

    def StateAll(self):
        status = self.detector.run_status
        self.state = self.StateMap[status], status.name

    def StateOne(self, axis):
        return self.state

    def ReadOne(self, axis):
        if self.acq is None:
            raise ValueError('Not in acquisition!')
        if self.acq.frames_ready:
            return next(self.acq)[1].tolist()

    def StartOne(self, axis, value):
        self._stop()
        self.acq = iter(self.detector.acquisition(progress_interval=None))

    def LoadOne(self, axis, value, repetitions, latency):
        self.detector.exposure_time = value
        self.detector.nb_frames = 1
        self.detector.nb_cycles = 1

    def AbortOne(Self, axis):
        if not self._stop():
            self.detector.stop_acquisition()

    def SetCtrlPar(self, name, value):
        if name in dir(self.detector):
            setattr(self.detector, name, value)
        else:
            return super().SetCtrlPar(name, value)

    def GetCtrlPar(self, name):
        if name in dir(self.detector):
            return getattr(self.detector, name)
        else:
            return super().GetCtrlPar(name)

    def SetAxisExtraPar(self, axis, name, value):
        self.SetCtrlPar(name, value)

    def GetAxisExtraPar(self, axis, name):
        return self.GetCtrlPar(name)

