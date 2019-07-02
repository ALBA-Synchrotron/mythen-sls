import pathlib

import yaml
import numpy




def save(settings, fname):
    with open(fname, 'wt') as fobj:
        return yaml.safe_dump(settings, fobj)


def load(fname):
    with open(fname, 'rt') as fobj:
        return yaml.safe_load(fobj)

# -----------------------------------------------------------------------------
# functions to handle original setup configuration. They are used to translate
# from the old to new configuration style.
# They consist of:
# 1. for each setting (standard, fast, ...):
#  1.1 N x <setting>/noise.<N serial nb>
#  1.2 N x <setting>/calibration.<N serial nb>
# 2. 1 bad channels file (<name>.chans)
# 3. 1 angular conversion file
# (N is nb of modules. For mythen this is 6)

def _load_bad_channels(fname):
    return numpy.loadtxt(fname, dtype=int)


def _load_calibration(fname):
    with open(fname, 'rt') as fobj:
        data = fobj.read()
    offset, gain = data.strip().split()
    return float(offset), float(gain)


def _load_module_settings(fname, nb_dacs=6, nb_channels=128, nb_chips=10): # noise file?
    chips = [dict(channels=[], register=None)
             for index in range(nb_chips)]
    module = {}
    with open(fname, 'rt') as fobj:
        module['dacs'] = dacs = []
        for dac_idx in range(nb_dacs):
            name, value = fobj.readline().split()
            dacs.append(int(value))
        module['chips'] = chips = []
        for chip_idx in range(nb_chips):
            name, value = fobj.readline().split()
            assert name == 'outBuffEnable'
            chip_register = int(value)
            channels = []
            for channel_idx in range(nb_channels):
                items = fobj.readline().split()
                trim, compen, anen, calen, outcomp, counts = map(int, items)
                register = (trim & 0x3F) | (compen << 9) | (anen << 8) | \
                           (calen << 7) | (outcomp << 10) | (counts << 11)
                channels.append(register)
            chips.append(dict(register=chip_register, channels=channels))
    return module


def _load_all_settings(basefname, module_serial_numbers, nb_dacs=6,
                       nb_channels=128, nb_chips=10):
    return [_load_module_settings(basefname + '.' + serial_number, nb_dacs,
                                  nb_channels, nb_chips)
            for serial_number in module_serial_numbers]


def _load_angular_conversion(fname):
    result = {}
    with open(fname, 'rt') as fobj:
        for line in fobj:
            fields = line.split()
            mod = dict(module=int(fields[1]),
                       center=float(fields[3]), center_error=float(fields[5]),
                       conversion=float(fields[7]), conversion_error=float(fields[9]),
                       offset=float(fields[11]), offset_error=float(fields[13]))
            result[mod['module']] = mod
    return result


def _convert(module_serial_numbers, settings_base_dir, settings,
             bad_channels_filename, angular_conversion_filename):
    calibration = {}
    for setting in settings:
        modules = []
        for sn in module_serial_numbers:
            set_fname = os.path.join(settings_base_dir, 'noise.' + sn)
            calib_fname = os.path.join(settings_base_dir, 'calibration.' + sn)
            module = _load_module_settings(sfname)
            module['offset'], module['gain'] = _load_calibration(calib_fname)
            module['serial_number'] = sn
            modules.append(module)
        calibration[setting] = dict(modules=modules)
    bad_channels = _load_bad_channels(bad_channels_filename)
    ang_conv = _load_angular_conversion(angular_conversion_filename)
    return dict(calibration=calibration, angular_conversion=ang_conv,
                bad_channels=bad_channels)
