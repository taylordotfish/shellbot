# Copyright (C) 2015-2016 taylor.fish <contact@taylor.fish>
#
# This file is part of shellbot.
#
# shellbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# shellbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with shellbot.  If not, see <http://www.gnu.org/licenses/>.
#
# See EXCEPTIONS for additional permissions.

from locale import getpreferredencoding
from queue import Queue
from subprocess import Popen, PIPE, STDOUT, TimeoutExpired
import os
import pwd
import selectors
import signal
import time


class CommandRunner:
    def __init__(self, timeout, cwd=None, user=None):
        self.user = user
        self.cwd = cwd
        self.timeout = timeout

        self.shell = ["/bin/bash", "-c"]
        self.output_limit = 100000
        self.path = ":".join([
            "/bin",
            "/usr/bin",
            "/usr/games",
            "/usr/local/bin",
            "/usr/local/games"
        ])

        self.queue = Queue()
        self.stop = False
        self.state = 0

    def get_subprocess(self, command):
        preexec = None
        if self.user:
            info = pwd.getpwnam(self.user)
            preexec = setid(info.pw_uid, info.pw_gid)
        return Popen(
            self.shell + [command], stdin=PIPE, stdout=PIPE, stderr=STDOUT,
            cwd=self.cwd, env={"PATH": self.path}, preexec_fn=preexec,
            start_new_session=True)

    def get_output(self, process):
        output = b""
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        end_time = time.monotonic() + self.timeout
        while len(output) <= self.output_limit:
            time_remaining = end_time - time.monotonic()
            if time_remaining < 0 or not selector.select(time_remaining):
                break
            data = process.stdout.read1(1024)
            if not data:
                break
            output += data
        selector.close()
        return output

    def run(self, command):
        process = self.get_subprocess(command)
        output = self.get_output(process)

        # Note: Processes which call setsid(), setpgrp(),
        # or similar functions won't be killed.
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)

        try:
            process.wait(self.timeout / 2)
        except TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
        return output.decode(getpreferredencoding(), "ignore").splitlines()

    def enqueue(self, command, callback, args):
        self.queue.put((command, callback, args, self.state))

    def reset(self):
        self.state += 1
        self.queue.put(None)

    def stop(self):
        self.stop = True
        self.reset()

    def loop(self):
        while not self.stop:
            item = self.queue.get()
            if item is not None:
                command, callback, args, state = item
                if state == self.state:
                    output = self.run(command)
                if state == self.state:
                    callback(*args, output)
        self.stop = False


def setid(uid, gid):
    assert uid != 0
    assert gid != 0

    def result():
        os.setgid(uid)
        os.setuid(gid)
    return result
