import warnings

import yaml

import sls.protocol


def load_mythen(mythen, fname):
    if fname.endswith('.conf'):
        warnings.warn('{} in old configuration format'.format(fname))
        config = _parse(fname)
    else:
        config = load(fname)
    if 'hostname' in config:
        assert mythen.conn_ctrl.addr[0] == config['hostname']
        assert mythen.conn_stop.addr[0] == config['hostname']
    if 'port' in config:
        assert mythen.conn_ctrl.addr[1] == config['port']
    if 'stopport' in config:
        assert mythen.conn_stop.addr[1] == config['stopport']
    if 'nmod' in config:
        mythen.set_nb_modules(config['nmod'])
        assert mythen.get_nb_modules() == config['nmod']
    if 'waitstates' in config:
        mythen.wait_states = config['waitstates']
        assert mythen.wait_states == config['waitstates']
    if 'setlength' in config:
        mythen.signal_length = config['setlength']
        assert mythen.signal_length == config['setlength']
    if 'clkdivider' in config:
        mythen.clock_divider = config['clkdivider']
        assert mythen.clock_divider == config['clkdivider']
    for i in range(4):
        key = 'extsig:{}'.format(i)
        if key in config:
            value = config[key].upper()
            sig = sls.protocol.ExternalSignal[value]
            mythen.set_external_signal(i, sig)
            assert mythen.get_external_signal(i) == sig
    if 'master' in config:
        assert config['master'] == -1
        mythen.master_mode = sls.protocol.MasterMode.NO_MASTER
    if 'sync' in config:
        mode = sls.protocol.SynchronizationMode[config['sync'].upper()]
        mythen.synchronization_mode = mode
        assert mythen.synchronization_mode == mode
    if 'exptime' in config:
        mythen.exposure_time = config['exptime']
    if 'frames' in config:
        mythen.nb_frames = config['frames']
    if 'cycles' in config:
        mythen.nb_cycles = config['cycles']


def save_mythen(mythen, fname):
    config = dict(
        hostname=mythen.conn_ctrl.addr[0],
        port=mythen.conn_ctrl.addr[1],
        stopport=mythen.conn_stop.addr[1],
        nmod=mythen.get_nb_modules(),
        waitstates=mythen.wait_states,
        setlength=mythen.signal_length,
        clkdivider=mythen.clock_divider,
        sync=mythen.synchronization_mode.name.lower(),
        exptime=mythen.exposure_time,
        frames=mythen.nb_frames,
        cycles=mythen.nb_cycles)
    for i in range(4):
        key = 'extsig:{}'.format(i)
        config[key] = mythen.get_external_signal(i).name.lower()
    save(config, fname)


def save(config, fname):
    with open(fname, 'wt') as fobj:
        return yaml.safe_dump(config, fobj)


def load(fname):
    with open(fname, 'rt') as fobj:
        return yaml.safe_load(fobj)


## Handle old configuration format

def _decode(k, v):
    if k[1] == ':':
        k = k[2:]
    try:
        return k, int(v)
    except ValueError:
        try:
            return k, float(v)
        except ValueError:
            pass
    return k, v


def _load(fname):
    result = {}
    with open(fname, 'rt') as fobj:
        for line in fobj:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            k, v = line.split(' ', 1)
            result[k] = v
    return result
            

def _parse(fname):
    return dict(_decode(k, v) for k, v in _load(fname).items())

