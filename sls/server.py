import logging
import functools

from gevent.server import StreamServer

from .protocol import *

log = logging.getLogger('SLSServer')


def sanitize_config(config):
    config.setdefault('ctrl_port', DEFAULT_CTRL_PORT)
    return config


class Detector:

    def __init__(self, config):
        self.config = config

    @property
    def type(self):
        return self.config['type']


def handle_ctrl(det, sock, addr):
    log.info('connected %s', addr)
    fileobj = sock.makefile(mode='rb')
    cmd = fileobj.read(1)
    cmd_code = CommandCode(struct.unpack('<i', cmd))
    print(cmd_code)
    if cmd_code == CommandCode.GET_DETECTOR_TYPE:
        arg = int(fileobj.read(1))
        if arg == -1:
            return det.type
    sock.close()
    log.info('disconnected %s', addr)


def run(config):
    config = sanitize_config(config)
    ctrl_port = config['ctrl_port']
    detector = Detector(config)
    server = StreamServer(('', ctrl_port), functools.partial(handle_ctrl, detector))
    server.serve_forever()


def main(args=None):
    fmt = '%(levelname)s %(asctime)-15s %(name)s: %(message)s'
    logging.basicConfig(format=fmt, level='INFO')
    config = dict(ctrl_port=DEFAULT_CTRL_PORT)
    run(config)


if __name__ == '__main__':
    main()
