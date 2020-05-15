# sls detector

The sls detector python library. It is being used at
[ALBA - BL04 MSPD](https://www.cells.es/en/beamlines/bl04-mspd)
beamline to control a SLS Mythen II detector.

It is built as a successor of the long lived C++ slsDetectorLibrary.

It should be fairly easy to support other detectors of the SLS
family.

The library provides complete remote control of a Mythen II detector,
a fairly complete simulator and a [Lima](https://github.com/esrf-bliss/Lima)
camera plugin with a tango device class.
There is also an experimental [Sardana](https://sardana-controls.org/)
1D controller which is not currently being used (the
[Sardana Lima 2D controller](https://github.com/ALBA-Synchrotron/sardana-limaccd)
is being used instead).

A simple GUI based on [PyQt5]() and [pyqtgraph]() is also provided. It
is intented for test purposes only.


## Installation

From within your favorite python environment type on the command line:

```$ pip install sls-detector```


## Library

The library can be used with:

```python
from sls.client import Detector
from sls.protocol import RunStatus


mythen = Detector('bl04mythen')

print(mythen.energy_threshold)

assert mythen.run_status == RunStatus.IDLE

mythen.dynamic_range = 32

with mythen.acquisition(exposure_time=0.1, nb_frames=10) as acq:
    for event_type, data in mythen.acquisition():
        if event_type == 'frame':
            print(data)

```

(more examples in the [examples/](examples/) directory)

## Simulator

Before using the simulator make sure all dependencies are installed with:

```$ pip install sls-detector[simulator]```

Write a simple [TOML](https://github.com/toml-lang/toml) configuration file describing the detector(s) you
want to expose. Example:

```toml
# mythen.toml

[bl04mythen1]
ctrl_port = 1952
stop_port = 1953
```

Run the simulator with:

```terminal
$ sls-simulator --log-level=DEBUG -c mythen.toml
INFO 2020-05-15 08:46:02,531 root: preparing to run...
INFO 2020-05-15 08:46:02,533 SLSServer.Detector(bl04mythen1): Ready to accept requests
```

You will now be able to access the simulator in exactly the same way as a real detector:

```python
from sls.client import Detector


mythen = Detector('localhost')

print(mythen.energy_threshold)
```

## Lima

Before using lima make sure lima is properly installed.

*From the command line*

```terminal
$ sls-lima --host=bl04mythen -n 10 -e 0.25 -d /tmp/mythen --saving-format=EDF --saving-prefix=myth_
Last image Ready = 10/10
Took 2.5158393383026123s
```

*As a library*

```python
from sls.client import Detector
from sls.lima.camera import get_ctrl
from Lima.Core import AcqRunning

ctrl = get_ctrl('bl04mythen')  # a Lima.Core.CtControl
acq = ctrl.acquisition()
acq.setAcqExpoTime(0.1)
acq.setAcqNbFrames(10)
ctrl.prepareAcq()
ctrl.startAcq()
while ctrl.getStatus().AcquisitionStatus == AcqRunning:
    print('Running... Waiting to finish!')
    time.sleep(0.1)
print('Finished!')
```

*As a lima tango server*

First, register a lima mythen tango server.

The LimaCCDs device should have the `LimaCameraType` property set to `MythenSLS`

You can start the Lima tango device server with the LimaCCDs script or with:

```terminal
$ sls-lima-tango-server <lima tango instance name>
```

## GUI

A simple Qt GUI is provided. So far, it is intended for test purposes only.

Before launching, make sure it is properly installed with:

```$ pip install sls-detector[gui]```

Launch it with:

```$ sls-gui --host=bl04mythen```


That's all folks!