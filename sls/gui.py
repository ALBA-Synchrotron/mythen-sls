import os
import time
import threading
import pkg_resources

import numpy
import pyqtgraph
from pyqtgraph.Qt import QtGui, QtCore, uic

UI_FILENAME = pkg_resources.resource_filename('sls', 'gui.ui')


class MythenGUI(QtGui.QMainWindow):

    newFrame = QtCore.Signal(object)
    newStats = QtCore.Signal(object)

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        uic.loadUi(UI_FILENAME, baseinstance=self)
        self.plot = self.gv.addPlot(title='Current Frame')
        self.image = pyqtgraph.ImageItem(border='w')
        view = self.gv.addViewBox()
        view.addItem(self.image)
        self.plot.showGrid(x=True, y=True)
        self.plot.setLabel('left', 'Counts')
        self.plot.setLabel('bottom', 'Channel')
        self.curve = self.plot.plot()
        self.central_widget.layout().insertWidget(0, self.gv, 1)
        self.acq_button.clicked.connect(self.start_acquisition)
        self.stop_button.clicked.connect(self.stop_acquisition)
        self.newFrame.connect(self._on_new_frame)
        self.newStats.connect(self._on_new_stats)

    def _on_new_frame(self, frame):
        data, index = frame['data'], frame['index']
        self.curve.setData(data)
        self.frame_nb.setText(str(index + 1))
        self.image_data[index, :] = data
        self.image.setImage(self.image_data)

    def _on_new_stats(self, stats):
        self.exposure_time_left.setText('{:4.2f} s'.format(stats['time_left']))

    def start_acquisition(self):
        self.acq_button.setEnabled(False)
        self.frame_nb.setText('0')
        self.image_data = numpy.zeros((6*10*128, self.nb_frames.value()), dtype='<i4').T
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
