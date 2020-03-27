import queue
import threading

from sls.client import Detector, RunStatus
from sls.acquisition import AcquisitionThread

from sardana import State, DataAccess
from sardana.pool import AcqSynch
from sardana.pool.controller import OneDController, Description, Access, \
    Type, Memorize, NotMemorized, MaxDimSize


class MythenSLSController(OneDController):

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
        if self.acq and self.acq.thread.is_alive():
            self.state = State.Running, 'running acquisition'
        else:
            status = self.detector.run_status
            self.state = self.StateMap[status], status.name

    def StateOne(self, axis):
        return self.state

    def ReadOne(self, axis):
        if self.acq is None:
            raise ValueError('Not in acquisition!')
        synch = self.GetCtrlPar('synchronization')
        if synch == AcqSynch.SoftwareStart:
            frames = []
            while not self.acq.queue.empty():
                data = self.acq.queue.get()
                if isinstance(data, Exception):
                    raise data
                frames.append(data)
            return frames
        else:
            if self.acq.queue.empty():
                return None
            else:
                data = self.acq.queue.get()
                if isinstance(data, Exception):
                    raise data
                return data

    def StartOne(self, axis, value):
        self.acq.start()

    def LoadOne(self, axis, value, repetitions, latency):
        self.acq = AcquisitionThread(self.detector, exposure_time=value,
                                     nb_frames=repetitions, nb_cycles=1)
        self.acq.prepare()

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
