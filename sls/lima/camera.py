# -*- coding: utf-8 -*-
#
# This file is part of the sls project
#
# Copyright (c) 2019 ALBA Synchrotron
# Distributed under the GPL license. See LICENSE for more info.

import os
import time
import logging
import threading

import numpy

from Lima.Core import (
    HwInterface, HwDetInfoCtrlObj, HwSyncCtrlObj, HwBufferCtrlObj, HwCap,
    HwFrameInfoType, SoftBufferCtrlObj, Size, Point, FrameDim, Roi, Bpp32,
    IntTrig, IntTrigMult, Timestamp, AcqReady, CtControl, CtSaving)

from sls.client import Detector
from sls.protocol import DEFAULT_CTRL_PORT, DEFAULT_STOP_PORT


Status = HwInterface.StatusType


class Sync(HwSyncCtrlObj):

    trig_mode = IntTrig

    def __init__(self, detector):
        self.detector = detector
        super().__init__()

    def checkTrigMode(self, trig_mode):
        return trig_mode in (IntTrig, IntTrigMult)

    def setTrigMode(self, trig_mode):
        if not self.checkTrigMode(trig_mode):
            raise ValueError('Unsupported trigger mode')
        self.trig_mode = trig_mode

    def getTrigMode(self):
        return self.trig_mode

    def setExpTime(self, exp_time):
        self.detector.exposure_time = exp_time

    def getExpTime(self):
        return self.detector.exposure_time

    def setLatTime(self, lat_time):
        self.latency_time = lat_time

    def getLatTime(self):
        return self.latency_time

    def setNbHwFrames(self, nb_frames):
        self.detector.nb_frames = nb_frames

    def getNbHwFrames(self):
        return self.detector.nb_frames

    def getValidRanges(self):
        return self.ValidRangesType(10E-9, 1E6, 10E-9, 1E6)


class DetInfo(HwDetInfoCtrlObj):

    image_type = Bpp32
    image_size = Size(6*10*128, 1)

    def __init__(self, detector):
        self.detector = detector
        super().__init__()

    def getMaxImageSize(self):
        return self.image_size

    def getDetectorImageSize(self):
        return self.image_size

    def getDefImageType(self):
        return type(self).image_type

    def getCurrImageType(self):
        return self.image_type

    def setCurrImageType(self, image_type):
        self.image_type = image_type

    def getPixelSize(self):
        return (1.0, 1.0)

    def getDetectorType(self):
        return "MythenSLS"

    def getDetectorModel(self):
        return "Mythen-II"

    def registerMaxImageSizeCallback(self, cb):
        pass

    def unregisterMaxImageSizeCallback(self, cb):
        pass


class Interface(HwInterface):

    def __init__(self, detector):
        super().__init__()
        self.detector = detector
        self.det_info = DetInfo(detector)
        self.sync = Sync(detector)
        self.buff = SoftBufferCtrlObj()
        self.caps = list(map(HwCap, (self.det_info, self.sync, self.buff)))
        self._status = Status.Ready
        self._nb_acquired_frames = 0
        self._acq_thread = None

    def getCapList(self):
        return self.caps

    def reset(self, reset_level):
        pass

    def prepareAcq(self):
        nb_frames = self.sync.getNbHwFrames()
        frame_dim = self.buff.getFrameDim()
        frame_infos = [HwFrameInfoType() for i in range(nb_frames)]
        self._nb_acquired_frames = 0
        self._acq_thread = threading.Thread(target=self._acquire,
                                            args=(frame_dim, frame_infos))

    def startAcq(self):
        self._acq_thread.start()

    def stopAcq(self):
        self.detector.stop_acquisition()
        if self._acq_thread:
            self._acq_thread.join()

    def getStatus(self):
        s = Status()
        s.set(self._status)
        return s

    def getNbHwAcquiredFrames(self):
        return self._nb_acquired_frames

    def _acquire(self, frame_dim, frame_infos):
        try:
            self._acquisition_loop(frame_dim, frame_infos)
        except Exception as err:
            print('Error occurred: {!r}'.format(err))

    def _acquisition_loop(self, frame_dim, frame_infos):
        frame_size = frame_dim.getMemSize()
        buffer_mgr = self.buff.getBuffer()
        start_time = time.time()
        buffer_mgr.setStartTimestamp(Timestamp(start_time))
        self._status = Status.Exposure
        for frame_nb, frame in enumerate(self.detector.acquire()):
            self._status = Status.Readout
            buff = buffer_mgr.getFrameBufferPtr(frame_nb)
            # don't know why the sip.voidptr has no size
            buff.setsize(frame_size)
            data = numpy.frombuffer(buff, dtype='<i4')
            data[:] = frame
            frame_info = frame_infos[frame_nb]
            frame_info.acq_frame_nb = frame_nb
            buffer_mgr.newFrameReady(frame_info)
            self._nb_acquired_frames += 1
            self._status = Status.Exposure
        self._status = Status.Ready


def get_ctrl(host, ctrl_port=DEFAULT_CTRL_PORT, stop_port=DEFAULT_STOP_PORT):
    detector = Detector(host, ctrl_port=ctrl_port, stop_port=stop_port)
    interface = Interface(detector)
    ctrl = CtControl(interface)
    return ctrl


def run(options):
    ctrl = get_control(options.host, options.ctrl_port, options.stop_port)

    acq = ctrl.acquisition()
    acq.setAcqExpoTime(options.exposure_time)
    acq.setAcqNbFrames(options.nb_frames)

    saving = ctrl.saving()
    saving.setFormat(options.saving_format)
    saving.setPrefix(options.saving_prefix)
    saving.setSuffix(options.saving_suffix)
    if options.saving_directory:
        saving.setSavingMode(saving.AutoFrame)
        saving.setDirectory(options.saving_directory)
    print(saving.getParameters())

    ready_event = threading.Event()

    class ISCB(CtControl.ImageStatusCallback):
        end_time = None
        def imageStatusChanged(self, image_status):
            frame = image_status.LastImageReady + 1
            msg = 'Last image Ready = {}/{}'.format(frame, options.nb_frames)
            print(msg, end='\r', flush=True)
            if frame == options.nb_frames:
                self.end_time = time.time()
                ready_event.set()

    cb = ISCB()
    ctrl.registerImageStatusCallback(cb)

    ctrl.prepareAcq()
    start = time.time()
    ctrl.startAcq()
    ready_event.wait()
    print()
    while ctrl.getStatus().AcquisitionStatus != AcqReady:
        print('Running... Waitting to finish!')
    print('Took {}s'.format(cb.end_time-start))

    return ctrl


def get_options(namespace, enum):
    return {name: getattr(namespace, name) for name in dir(namespace)
            if isinstance(getattr(namespace, name), enum)}


def main(args=None):
    import argparse
    file_format_options = get_options(CtSaving, CtSaving.FileFormat)
    breakpoint()
    file_format_suffix = {f: '.{}'.format(f.replace('HDF5', 'h5').replace('Format', '').lower())
                          for f in file_format_options}
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--ctrl-port', default=DEFAULT_CTRL_PORT)
    parser.add_argument('--stop-port', default=DEFAULT_STOP_PORT)
    parser.add_argument('-n', '--nb-frames', default=10, type=int)
    parser.add_argument('-e', '--exposure-time',default=0.1, type=float)
    parser.add_argument('-l', '--latency-time', default=0.0, type=float)
    parser.add_argument('-d', '--saving-directory', default=None, type=str)
    parser.add_argument('--saving-format', default='EDF', type=str,
                        choices=sorted(file_format_options))
    parser.add_argument('-p', '--saving-prefix', default='image_', type=str)
    parser.add_argument('-s', '--saving-suffix', default='__AUTO_SUFFIX__',
                        type=str)
    parser.add_argument('--log-level', help='log level', type=str,
                        default='INFO',
                        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'])
    options = parser.parse_args(args)

    log_level = getattr(logging, options.log_level.upper())
    log_fmt = '%(levelname)s %(asctime)-15s %(name)s: %(message)s'
    logging.basicConfig(level=log_level, format=log_fmt)

    options.saving_format_name = options.saving_format
    options.saving_format = file_format_options[options.saving_format]
    if options.saving_suffix == '__AUTO_SUFFIX__':
        options.saving_suffix = file_format_suffix[options.saving_format_name]
    run(options)


if __name__ == '__main__':
    ctrl = main()
