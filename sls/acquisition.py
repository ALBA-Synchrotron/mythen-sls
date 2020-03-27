import queue
import threading


from .protocol import fetch_frames, start_acquisition, stop_acquisition, SLSError


class StopAcquisition(Exception):
    pass


class BaseAcquisition:

    def __init__(self, detector, **opts):
        self.nb_frames = opts.setdefault('nb_frames', 1)
        self.nb_cycles = opts.setdefault('nb_cycles', 1)
        self.exposure_time = opts.setdefault('exposure_time', 1)
        self.detector = detector
        self.opts = opts
        self.nb_acquired_frames = 0

    def __len__(self):
        return self.nb_frames * self.nb_cycles

    def prepare(self):
        for key, value in self.opts.items():
            setattr(self.detector, key, value)
        self.info = self.detector.update_client()
        assert self.nb_frames == self.info['nb_frames']
        assert self.nb_cycles == self.info['nb_cycles']

    def start(self):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError


class AcquisitionIter(BaseAcquisition):

    def prepare(self):
        super().prepare()
        self._acq = self._start_and_acquire()

    def start(self):
        result = next(self)
        assert result is None

    def stop(self):
        if self._acq is None:
            self.detector.stop_acquisition()
        else:
            try:
                self._acq.throw(StopAcquisition())
            except StopIteration:
                pass

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._acq)

    def _start_and_acquire(self):
        detector, info = self.detector, self.info
        frame_size = info['data_bytes']
        dynamic_range = info['dynamic_range']
        conn = detector.conn_ctrl
        with conn:
            start_acquisition(conn)
            try:
                # yield after start to give change for other channels to
                # start as concurrently as possible
                yield None
                for frame in fetch_frames(conn, frame_size, dynamic_range):
                    yield frame
            except StopAcquisition:
                detector.stop_acquisition()
                return
            except BaseException:
                detector.stop_acquisition()
                raise


class AcquisitionThread(AcquisitionIter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = queue.Queue()
        self._stopping = False

    def prepare(self):
        super().prepare()
        self.thread = threading.Thread(target=self._acq_loop)
        self.thread.daemon = True

    def start(self):
        super().start()
        self.thread.start()

    def stop(self):
        self._stopping = True
        self.detector.stop_acquisition()

    def _acq_loop(self):
        try:
            for frame in self:
                self.queue.put(frame)
        except SLSError as err:
            if self._stopping:
                return
            self.queue.put(err)
        except Exception as err:
            self.queue.put(err)
