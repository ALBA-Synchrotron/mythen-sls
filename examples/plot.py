import argparse
import threading

import sls.client
import pyqtgraph.Qt

def run(options):
    app = pyqtgraph.Qt.QtGui.QApplication([])

    plot = pyqtgraph.plot()
    curve = plot.plot()
    plot.show()

    mythen = sls.client.Detector(options.host)
    mythen.nb_frames = options.nb_frames
    mythen.exposure_time = options.exposure_time

    def acquire(curve):
        for frame in mythen.acquire():
            curve.setData(frame)

    th = threading.Thread(target=acquire, args=(curve,), daemon=True)
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
