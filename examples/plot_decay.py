import argparse
import threading

import pyqtgraph
from pyqtgraph.Qt import QtGui, QtCore

import sls.client

N = 5


class QDetector(QtCore.QObject):
    newFrame = QtCore.Signal(object)


def run(options):
    app = QtGui.QApplication([])

    plot = pyqtgraph.plot()
    plot.show()

    mythen = sls.client.Detector(options.host)
    mythen.nb_frames = options.nb_frames
    mythen.exposure_time = options.exposure_time
    qmythen = QDetector()

    def acquire():
        for frame in mythen.acquire():
            qmythen.newFrame.emit(frame)

    curves = []

    def on_new_frame(frame):
        if len(curves) == N:
            plot.removeItem(curves[0])
            curves.pop(0)
        for i, curve in enumerate(curves[::-1]):
            v = 100 - 20 * i
            curve.setPen(4*(v,))
        curve = plot.plot(frame)
        curve.setPen('r')
        curves.append(curve)

    qmythen.newFrame.connect(on_new_frame)

    th = threading.Thread(target=acquire, daemon=True)
    th.start()

    app.exec_()


def main(args=None):
    p = argparse.ArgumentParser()
    p.add_argument('--nb-frames', default=10, type=int)
    p.add_argument('--exposure-time', default=0.1, type=float)
    p.add_argument('--host', default='localhost')
    opts = p.parse_args(args)
    run(opts)


if __name__ == '__main__':
    main()
