import argparse
import threading

import numpy as np
import pyqtgraph as pg
import pyqtgraph.Qt as qt
import pyqtgraph.opengl as pggl

from sls.client import Detector

SIZE = 7680

GRID_N_X = 100
GRID_N_Z = 20

GRID_SIZE_Y = 2000


class QDetector(qt.QtCore.QObject):

    newFrame = qt.QtCore.Signal(object)


def run(options):
    app = qt.QtGui.QApplication([])

    n = options.nb_frames

    w = pggl.GLViewWidget()
    w.opts['distance'] = 10000
    w.show()
    w.setWindowTitle('Mythen Acquisition')

    gx = pggl.GLGridItem()
    gx.setSize(GRID_N_Z, n)
    gx.scale(GRID_N_X, GRID_SIZE_Y/n, 1)
    gx.rotate(90, 0, 1, 0)
    gx.translate(-SIZE/2, 0, GRID_SIZE_Y/2)
    w.addItem(gx)

    gy = pggl.GLGridItem()
    gy.setSize(GRID_N_X, GRID_N_Z)
    gy.scale(SIZE/GRID_N_X, GRID_N_X, 1)
    gy.rotate(90, 1, 0, 0)
    gy.translate(0, -GRID_SIZE_Y/2, GRID_SIZE_Y/2)
    w.addItem(gy)

    gz = pggl.GLGridItem()
    gz.setSize(GRID_N_X, n)
    gz.scale(SIZE/GRID_N_X, GRID_SIZE_Y/n, 1)
    gz.translate(0, 0, 0)
    w.addItem(gz)

    y = np.linspace(-GRID_SIZE_Y // 2, GRID_SIZE_Y // 2, n)
    x = np.arange(SIZE) - SIZE / 2

    def on_new_frame(data):
        plt = pggl.GLLinePlotItem(
            pos=data['line'], color=data['color'], antialias=True)
        w.addItem(plt)

    def acq_loop():
        for i, frame in enumerate(mythen.acquire()):
            yi = np.array([y[i]] * frame.size)
            data = dict(
                frame=frame,
                line=np.vstack((x, yi, frame)).T,
                color=pg.glColor((i, n * 1.3)))
            qmythen.newFrame.emit(data)

    mythen = Detector(options.host)
    mythen.nb_frames = n
    mythen.exposure_time = options.exposure_time
    qmythen = QDetector()
    qmythen.newFrame.connect(on_new_frame)

    th = threading.Thread(target=acq_loop, daemon=True)
    th.start()

    app.exec_()


def main(args=None):
    p = argparse.ArgumentParser()
    p.add_argument('--nb-frames', default=10, type=int)
    p.add_argument('--exposure-time', default=1, type=float)
    p.add_argument('--host', default='localhost')
    opts = p.parse_args(args)
    run(opts)


if __name__ == '__main__':
    main()
