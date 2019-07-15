from tango import DevState
from tango.server import Device, device_property
from sls.lima.camera import get_control
from sls.protocol import DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT


class Mythen(Device):

    host = device_property(dtype=str)
    ctrl_port = device_property(dtype=int, default_value=DEFAULT_CTRL_PORT)
    stop_port = device_property(dtype=int, default_value=DEFAULT_STOP_PORT)

    def init_device(self):
        super().init_device()
        self.set_state(DevState.ON)


def get_tango_specific_class_n_device():
    return Mythen.TangoClassClass, Mythen
