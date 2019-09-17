import fabric


class Server:

    process_name = '/mnt/flash/root/mythenDetectorServer'

    def __init__(self, host, user='root', password='pass'):
        self.host = host
        self.user = user
        self.password = password
        self._connection = None

    def _build_connection(self):
        return fabric.Connection(
                self.host, user=self.user,
                connect_kwargs=dict(password=self.password))
    @property
    def connection(self):
        if self._connection is None:
            self._connection = self._build_connection()
        return self._connection

    def run(self, *cmd, **kwargs):
        return self.connection.run(' '.join(cmd), hide=True, warn=True, **kwargs)

    def stop(self):
        proc = self.process_name.rsplit('/', 1)[-1]
        return self.run('killall', proc)

    def start(self):
        if self.is_running:
            raise RuntimeError('Server is already running')
        # problem: this actually never returns because fabric just waits for the
        # process to finish which it never does
        return self.run(self.process_name, '&')

    def restart(self):
        r1 = self.stop()
        r2 = self.start()
        return r1, r2

    @property
    def is_running(self):
        result = self.run('ps')
        return self.process_name in result.stdout
