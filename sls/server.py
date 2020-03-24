import os
import sys
import time
import logging
import subprocess

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
        return 'mythenDetectorServer' in self.processes

    @property
    def processes(self):
        return self.conn.run('ps', warn=True, hide=True).stdout

    def start(self):
        self.conn.run('/mnt/flash/root/mythenDetectorServer 1953 &',
                      warn=True, hide=True)
        return self.is_running

    def terminate(self):
        if self.is_running:
            self.log.info('stop server')
            self.conn.run('killall -q mythenDetectorServer', warn=True, hide=True)

    def hard_reset(self, sleep=time.sleep):
        self.log.info('start server')
        args = [sys.executable, '-m', 'sls.server', self.host, self.user,
                self.password]
        proc = subprocess.Popen(args, close_fds=True)
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.terminate()
            self.log.info('needed to terminate start server process manually')
        if not self.is_running:
            raise RuntimeError('Failed to restart server')


def restart_detector():
    host, user, password = sys.argv[1:4]
    kwargs = dict(password=password)
    conn = fabric.Connection(host, user=user, connect_kwargs=kwargs)
    conn.run('/mnt/flash/root/startDetector', warn=True)
    os.system('reset')


if __name__ == '__main__':
    restart_detector()
