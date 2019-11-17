import argparse

from sls.client import Detector


def acquisition(detector, exposure_time=1, nb_frames=1, nb_cycles=1, 
                progress_interval=0.25):
    templ = 'Current frame time left {{exposure_time_left:.3f}}s; ' \
            'Frame #{{nb_frames_finished:03}}/{:03}; ' \
            'Cycle #{{nb_cycles_finished:03}}/{:03};'.format(nb_frames, nb_cycles)
    acq = detector.acquisition(exposure_time=exposure_time,
        nb_frames=nb_frames, nb_cycles=nb_cycles,
        progress_interval=progress_interval)
    for event_type, event in acq:
        if event_type == 'progress':
            print(templ.format(**event), end='\n', flush=True)
        elif event_type == 'frame':
            print('frame!')


def run(options):
    detector = Detector(options.host)
    acquisition(detector, exposure_time=options.exposure_time,
        nb_frames=options.nb_frames, nb_cycles=options.nb_cycles,
        progress_interval=options.progress_interval)


def main(args=None):
    p = argparse.ArgumentParser()
    p.add_argument('--nb-frames', default=10, type=int)
    p.add_argument('--exposure-time', default=0.1, type=float)
    p.add_argument('--nb-cycles', default=1, type=int)
    p.add_argument('--progress-interval', default=0.25, type=float)
    p.add_argument('host')
    opts = p.parse_args(args)
    run(opts)


if __name__ == '__main__':
    main()
