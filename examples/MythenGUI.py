import time
import threading

import pyqtgraph
from pyqtgraph.Qt import QtGui, QtCore, uic


class MythenGUI(QtGui.QMainWindow):

    newFrame = QtCore.Signal(object)
    newStats = QtCore.Signal(object)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        panel = QtGui.QWidget()
        l = QtGui.QHBoxLayout(panel)
        plot = pyqtgraph.PlotWidget(name='P1')
        curve = plot.plot()
        form_l = QtGui.QFormLayout()
        l.addWidget(plot)
        l.addLayout(form_l)
        nb_frames = QtGui.QSpinBox()
        nb_frames.setValue(10)
        nb_frames.setMaximum(99999)
        exp_time = QtGui.QDoubleSpinBox()
        exp_time.setSuffix(' s')
        exp_time.setSingleStep(0.05)
        exp_time.setDecimals(2)
        exp_time.setValue(0.1)
        exp_time.setMaximum(1000)
        exp_time_left = QtGui.QLabel('---')
        frame_nb = QtGui.QLabel('---')
        acq = QtGui.QPushButton('acquire')
        stop = QtGui.QPushButton('stop')
        acq.clicked.connect(self.start_acquisition)
        stop.clicked.connect(self.stop_acquisition)
        form_l.addRow('Nb. frames', nb_frames)
        form_l.addRow('Exposure time', exp_time)
        form_l.addRow('Current frame time left', exp_time_left)
        form_l.addRow('Frames acquired', frame_nb)
        form_l.addRow(acq)
        form_l.addRow(stop)
        self.setWindowTitle('Myhen demo')
        self.setCentralWidget(panel)
        self.exposure_time = exp_time
        self.exposure_time_left = exp_time_left
        self.nb_frames = nb_frames
        self.frame_nb = frame_nb
        self.acq_button = acq
        self.plot = plot
        self.curve = curve
        self.newFrame.connect(self._on_new_frame)
        self.newStats.connect(self._on_new_stats)

    def _on_new_frame(self, frame):
        self.curve.setData(frame['data'])
        self.frame_nb.setText(str(frame['index']+1))

    def _on_new_stats(self, stats):
        self.exposure_time_left.setText('{:4.2f} s'.format(stats['time_left']))

    def start_acquisition(self):
        self.acq_button.setEnabled(False)
        self.frame_nb.setText('0')
        self.acq_thread = threading.Thread(target=self._acquire, daemon=True)
        if self.exposure_time.value() > 1:
            self.mon_thread = threading.Thread(target=self._monitor, daemon=True)
            self.mon_thread.start()
        else:
            self.exposure_time_left.setText('---')
        self.acq_thread.start()

    def stop_acquisition(self):
        self.detector.stop_acquisition()

    def _acquire(self):
        self.detector.nb_frames = self.nb_frames.value()
        self.detector.exposure_time = self.exposure_time.value()
        for i, frame in enumerate(self.detector.acquire()):
            self.newFrame.emit(dict(data=frame, index=i))
        self.acq_thread = None
        self.acq_button.setEnabled(True)

    def _monitor(self):
        while self.acq_thread is not None:
            stats = dict(time_left=self.detector.exposure_time_left)
            self.newStats.emit(stats)
            time.sleep(0.2)
        self.newStats.emit(dict(time_left=0))
        self.mon_thread = None


def run(options):
    import sls.client
    app = QtGui.QApplication([])
    detector = sls.client.Detector(options.host)
    gui = MythenGUI(detector)
    gui.show()
    app.exec_()


def main(args=None):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='localhost')
    opts = p.parse_args(args)
    run(opts)


if __name__ == '__main__':
    main()
