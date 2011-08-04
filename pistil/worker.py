# -*- coding: utf-8 -
#
# This file is part of pistil released under the MIT license. 
# See the NOTICE for more information.

from __future__ import with_statement

import logging
import os
import signal
import sys
import traceback


from gunicorn import util
from pistil.workertmp import WorkerTmp

class Worker(object):
    
    SIGNALS = map(
        lambda x: getattr(signal, "SIG%s" % x),
        "HUP QUIT INT TERM USR1 USR2 WINCH CHLD".split()
    )
    
    PIPE = []

    def __init__(self, age, ppid, timeout, conf, worker_args):
        self.age = age
        self.ppid = ppid
        self.timeout = timeout
        self.conf = conf
        self.worker_args = worker_args
        self.booted = False


        self.nr = 0
        self.max_requests = conf.get("max_requests", sys.maxint)
        self.alive = True
        self.log = logging.getLogger(__name__)
        self.debug = conf.get("debug", False)
        self.tmp = WorkerTmp(conf)

        self.on_init()

    def on_init(self):
        """ methode executed after worker initialization"""

    @property
    def pid(self):
        return os.getpid()

    def notify(self):
        """\
        Your worker subclass must arrange to have this method called
        once every ``self.timeout`` seconds. If you fail in accomplishing
        this task, the master process will murder your workers.
        """
        self.tmp.notify()

    def run(self):
        """\
        This is the mainloop of a worker process. You should override
        this method in a subclass to provide the intended behaviour
        for your particular evil schemes.
        """
        raise NotImplementedError()

    def on_init_process(self):
        """ method executed when we init a process """

    def init_process(self):
        """\
        If you override this method in a subclass, the last statement
        in the function should be to call this method with
        super(MyWorkerClass, self).init_process() so that the ``run()``
        loop is initiated.
        """
        util.set_owner_process(self.conf.get("uid", os.geteuid()),
                self.conf.get("gid", os.getegid()))

        # Reseed the random number generator
        util.seed()

        # For waking ourselves up
        self.PIPE = os.pipe()
        map(util.set_non_blocking, self.PIPE)
        map(util.close_on_exec, self.PIPE)
        
        # Prevent fd inherientence
        util.close_on_exec(self.tmp.fileno())
        self.init_signals()
        
        self.on_init_process()

        # Enter main run loop
        self.booted = True
        self.run()

    def init_signals(self):
        map(lambda s: signal.signal(s, signal.SIG_DFL), self.SIGNALS)
        signal.signal(signal.SIGQUIT, self.handle_quit)
        signal.signal(signal.SIGTERM, self.handle_exit)
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGWINCH, self.handle_winch)
            
    def handle_quit(self, sig, frame):
        self.alive = False

    def handle_exit(self, sig, frame):
        self.alive = False
        sys.exit(0)
        
    def handle_winch(self, sig, fname):
        # Ignore SIGWINCH in worker. Fixes a crash on OpenBSD.
        return
