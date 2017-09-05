import os
import pwd
import grp
import sys
import socket
import signal
import logging
import daemon.pidfile
import argparse
import threading
import cProfile

from pandaharvester.harvesterconfig import harvester_config
from pandaharvester.harvestercore import core_utils

# logger
_logger = core_utils.setup_logger('master')

# for singleton
master_instance = False
master_lock = threading.Lock()


# the master class which runs the main process
class Master(object):

    # constructor
    def __init__(self, single_mode=False, stop_event=None, daemon_mode=True):
        # initialize database and config
        self.singleMode = single_mode
        self.stopEvent = stop_event
        self.daemonMode = daemon_mode
        from pandaharvester.harvestercore.communicator_pool import CommunicatorPool
        self.communicatorPool = CommunicatorPool()
        from pandaharvester.harvestercore.queue_config_mapper import QueueConfigMapper
        self.queueConfigMapper = QueueConfigMapper()
        from pandaharvester.harvestercore.db_proxy_pool import DBProxyPool as DBProxy
        dbProxy = DBProxy()
        dbProxy.make_tables(self.queueConfigMapper)

    # main loop
    def start(self):
        # thread list
        thrList = []
        # Credential Manager
        from pandaharvester.harvesterbody.cred_manager import CredManager
        thr = CredManager(single_mode=self.singleMode)
        thr.set_stop_event(self.stopEvent)
        thr.execute()
        thr.start()
        thrList.append(thr)
        # Command manager
        from pandaharvester.harvesterbody.command_manager import CommandManager
        thr = CommandManager(self.communicatorPool, self.queueConfigMapper, single_mode=self.singleMode)
        thr.set_stop_event(self.stopEvent)
        thr.start()
        thrList.append(thr)
        # Cacher
        from pandaharvester.harvesterbody.cacher import Cacher
        thr = Cacher(self.communicatorPool, single_mode=self.singleMode)
        thr.set_stop_event(self.stopEvent)
        thr.execute()
        thr.start()
        thrList.append(thr)
        # Job Fetcher
        from pandaharvester.harvesterbody.job_fetcher import JobFetcher
        nThr = harvester_config.jobfetcher.nThreads
        for iThr in range(nThr):
            thr = JobFetcher(self.communicatorPool,
                             self.queueConfigMapper,
                             single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Propagator
        from pandaharvester.harvesterbody.propagator import Propagator
        nThr = harvester_config.propagator.nThreads
        for iThr in range(nThr):
            thr = Propagator(self.communicatorPool,
                             self.queueConfigMapper,
                             single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Monitor
        from pandaharvester.harvesterbody.monitor import Monitor
        nThr = harvester_config.monitor.nThreads
        for iThr in range(nThr):
            thr = Monitor(self.queueConfigMapper,
                          single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Preparator
        from pandaharvester.harvesterbody.preparator import Preparator
        nThr = harvester_config.preparator.nThreads
        for iThr in range(nThr):
            thr = Preparator(self.communicatorPool,
                             self.queueConfigMapper,
                             single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Submitter
        from pandaharvester.harvesterbody.submitter import Submitter
        nThr = harvester_config.submitter.nThreads
        for iThr in range(nThr):
            thr = Submitter(self.queueConfigMapper,
                            single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Stager
        from pandaharvester.harvesterbody.stager import Stager
        nThr = harvester_config.stager.nThreads
        for iThr in range(nThr):
            thr = Stager(self.queueConfigMapper,
                         single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # EventFeeder
        from pandaharvester.harvesterbody.event_feeder import EventFeeder
        nThr = harvester_config.eventfeeder.nThreads
        for iThr in range(nThr):
            thr = EventFeeder(self.communicatorPool,
                              self.queueConfigMapper,
                              single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        # Sweeper
        from pandaharvester.harvesterbody.sweeper import Sweeper
        nThr = harvester_config.sweeper.nThreads
        for iThr in range(nThr):
            thr = Sweeper(self.queueConfigMapper,
                          single_mode=self.singleMode)
            thr.set_stop_event(self.stopEvent)
            thr.start()
            thrList.append(thr)
        ##################
        # loop on stop event to be interruptable since thr.join blocks signal capture in python 2.7
        while True:
            if self.singleMode or not self.daemonMode:
                break
            self.stopEvent.wait(1)
            if self.stopEvent.is_set():
                break
        ##################
        # join
        if self.daemonMode:
            for thr in thrList:
                thr.join()


# dummy context
class DummyContext(object):
    def __enter__(self):
        return self

    def __exit__(self, *x):
        pass


# wrapper for stderr
class StdErrWrapper(object):
    def write(self, message):
        _logger.error(message)

    def fileno(self):
        return _logger.handlers[0].stream.fileno()


# main
def main(daemon_mode=True):
    # parse option
    parser = argparse.ArgumentParser()
    parser.add_argument('--pid', action='store', dest='pid', default=None,
                        help='pid filename')
    parser.add_argument('--single', action='store_true', dest='singleMode', default=False,
                        help='use single mode')
    parser.add_argument('--hostname_file', action='store', dest='hostNameFile', default=None,
                        help='to record the hostname where harvester is launched')
    parser.add_argument('--rotate_log', action='store_true', dest='rotateLog', default=False,
                        help='rollover log files before launching harvester')
    parser.add_argument('--profile_output', action='store', dest='profileOutput', default=None,
                        help='filename to save the results of profiler')
    options = parser.parse_args()
    uid = pwd.getpwnam(harvester_config.master.uname).pw_uid
    gid = grp.getgrnam(harvester_config.master.gname).gr_gid
    # hostname
    if options.hostNameFile is not None:
        with open(options.hostNameFile, 'w') as f:
            f.write(socket.getfqdn())
    # rollover log files
    if options.rotateLog:
        core_utils.do_log_rollover()
        if hasattr(_logger.handlers[0], 'doRollover'):
            _logger.handlers[0].doRollover()
    if daemon_mode:
        # redirect messages to stdout
        stdoutHandler = logging.StreamHandler(sys.stdout)
        stdoutHandler.setFormatter(_logger.handlers[0].formatter)
        _logger.addHandler(stdoutHandler)
        # collect streams not to be closed by daemon
        files_preserve = []
        for loggerName, loggerObj in logging.Logger.manager.loggerDict.iteritems():
            if loggerName.startswith('panda'):
                for handler in loggerObj.handlers:
                    if hasattr(handler, 'stream'):
                        files_preserve.append(handler.stream)
        sys.stderr = StdErrWrapper()
        # make daemon context
        dc = daemon.DaemonContext(stdout=sys.stdout,
                                  stderr=sys.stderr,
                                  uid=uid,
                                  gid=gid,
                                  files_preserve=files_preserve,
                                  pidfile=daemon.pidfile.PIDLockFile(options.pid))
    else:
        dc = DummyContext()
    with dc:
        if daemon_mode:
            _logger.info("start")

        # stop event
        stopEvent = threading.Event()

        # signal handlers
        def catch_sigkill(sig, frame):
            os.killpg(os.getpgrp(), signal.SIGKILL)

        def catch_sigterm(sig, frame):
            stopEvent.set()

        # set handler
        if daemon_mode:
            signal.signal(signal.SIGINT, catch_sigkill)
            signal.signal(signal.SIGHUP, catch_sigkill)
            signal.signal(signal.SIGTERM, catch_sigterm)
            signal.signal(signal.SIGUSR2, catch_sigterm)
        # start master
        master = Master(single_mode=options.singleMode, stop_event=stopEvent, daemon_mode=daemon_mode)
        if master is not None:
            if options.profileOutput is not None:
                cProfile.runctx('master.start()', globals(), locals(), options.profileOutput)
            else:
                master.start()
        if daemon_mode:
            _logger.info('terminated')


if __name__ == "__main__":
    main()
else:
    # started by WSGI
    with master_lock:
        if not master_instance:
            main(daemon_mode=False)
            master_instance = True
    # import application entry for WSGI
    from pandaharvester.harvestermessenger.apache_messenger import application
