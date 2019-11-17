import sys
import argparse

import tqdm

from sls.client import Detector


def acquisition_progress(detector, exposure_time=1, nb_frames=1, nb_cycles=1,
                         progress_interval=0.25):
    if nb_frames == 0:
        nb_frames = 1
    if nb_cycles == 0:
        nb_cycles = 1
    nb_steps = nb_frames * nb_cycles

    def postfix(time_left=exposure_time, frame_nb=0, cycle_nb=0):
        r = {}
        if exposure_time >= 1:
            r['F. ETA'] = '{:.2f}/{}s'.format(time_left, exposure_time)
        if nb_steps > 1:
            r['F#'] = '{}/{}'.format(frame_nb, nb_frames)
        if nb_cycles > 1:
            r['C#'] = '{}/{}'.format(cycle_nb, nb_cycles)
        return r

    fmt = '{l_bar}{bar}| {n:.1f}/{total_fmt} [{elapsed}<{remaining}]{postfix}]'
    with detector.acquisition(exposure_time=exposure_time,
        nb_frames=nb_frames, nb_cycles=nb_cycles,
        progress_interval=progress_interval) as acq:
        with tqdm.tqdm(acq, unit='frame', bar_format=fmt, postfix=postfix(),
                       ascii=True) as pbar:
            previous_step = 0
            for event_type, event in acq:
                if event_type == 'progress':
                    frame_nb = event['nb_frames_finished']
                    cycle_nb = event['nb_cycles_finished']
                    curr_time = event['exposure_time'] / exposure_time
                    time_left = event['exposure_time_left']
                    step = min(curr_time + frame_nb + nb_frames*cycle_nb, nb_steps)
                    pbar.set_postfix(**postfix(time_left, frame_nb, cycle_nb))
                    pbar.update(step-previous_step)
                    previous_step = step


def run(options):
    detector = Detector(options.host)
    acquisition_progress(detector, exposure_time=options.exposure_time,
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
