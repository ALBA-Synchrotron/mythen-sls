from tango import DevState, Util
from tango.server import Device, device_property, attribute
from sls.lima.camera import get_ctrl
from sls.protocol import DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT
from sls.protocol import RunStatus

class MythenSLS(Device):

    host = device_property(dtype=str)
    ctrl_port = device_property(dtype=int, default_value=DEFAULT_CTRL_PORT)
    stop_port = device_property(dtype=int, default_value=DEFAULT_STOP_PORT)

    def init_device(self):
        super().init_device()
        self.ctrl = get_control()

    @property
    def mythen(self):
        return self.ctrl.hwInterface().detector

    def dev_state(self):
        status = self.mythen.run_status
        if status in (RunStatus.WAITING, RunStatus.TRANSMITTING,
                      RunStatus.RUNNING):
            return DevState.RUNNING
        elif status == RunStatus.ERROR:
            return DevState.FAULT
        return DevState.ON

    def dev_status(self):
        return 'The device is {}'.format(self.mythen.run_status.name)

    @attribute
    def exposure_time_left(self):
        return self.mythen.exposure_time_left

    @attribute
    def nb_cycles_left(self):
        return self.mythen.nb_cycles_left

    @attribute
    def nb_frames_left(self):
        return self.mythen.nb_frames_left

    @attribute
    def progress(self):
        return self.mythen.progress

    @attribute
    def measurement_time(self):
        return self.mythen.measurement_time

    @attribute
    def energy_threshold(self):
        return self.mythen.energy_threshold

    @energy_threshold.setter
    def energy_threshold(self, energy_threshold):
        self.mythen.energy_threshold = energy_threshold



def get_tango_specific_class_n_device():
    return MythenSLS


_MYTHEN = None
def get_control(host=None, ctrl_port=DEFAULT_CTRL_PORT,
                stop_port=DEFAULT_STOP_PORT):
    global _MYTHEN
    if _MYTHEN is None:
        if host is None:
            # if there is no host property, use the server instance name
            host = Util.instance().get_ds_inst_name()
        _MYTHEN = get_ctrl(host, ctrl_port=ctrl_port, stop_port=stop_port)
    return _MYTHEN


def main():
    import Lima.Server.LimaCCDs
    Lima.Server.LimaCCDs.main()


if __name__ == '__main__':
    main()
