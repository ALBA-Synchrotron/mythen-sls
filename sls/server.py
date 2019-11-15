import time
import logging
import multiprocessing

import fabric


class Server:

    def __init__(self, host, user='root', password='pass'):
        self.host = host
        self.user = user
        self.password = password
        self._conn = None
        self.log = logging.getLogger('sls.Server({})'.format(host))

    def make_connection(self):
        kwargs = dict(password=self.password)
        return fabric.Connection(self.host, user=self.user, connect_kwargs=kwargs)

    @property
    def conn(self):
        if self._conn is None:
            self._conn = self.make_connection()
        return self._conn

    @property
    def is_running(self):
        result = self.conn.run('ps', warn=True, hide=True)
        return 'mythenDetectorServer' in result.stdout

    def terminate(self):
        if self.is_running:
            self.log.info('stop server')
            self.conn.run('killall -q mythenDetectorServer', warn=True, hide=True)

    def hard_reset(self, sleep=time.sleep):
        def start():
            self.log.info('start server')
            conn = self.make_connection()
            conn.run('/mnt/flash/root/startDetector &', warn=True, hide=True)
        proc = multiprocessing.Process(target=start)
        proc.start()
        sleep(1) # for sure 2s needed
        try:
            running, start = False, time.time()
            while ((time.time() - start) < 8) and not running:
                sleep(0.5)
                running = self.is_running
                self.log.info('loop until running (%s)', running)
        finally:
            if proc.is_alive():
                proc.terminate()
                proc.join()
                self.log.info('needed to terminate start server process manually')
        if not self.is_running:
            raise RuntimeError('Failed to restart server')
