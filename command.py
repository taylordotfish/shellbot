# Copyright (C) 2015 taylor.fish (https://github.com/taylordotfish)
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

from subprocess import Popen, PIPE, TimeoutExpired
import os
import pwd
import signal

env = {
    "PATH": ":".join([
        "/bin",
        "/usr/bin",
        "/usr/games",
        "/usr/local/bin",
        "/usr/local/games",
    ]),
}


def run_shell(command, user, cwd, timeout, kill_timeout):
    if user:
        info = pwd.getpwnam(user)
        preexec = setid(info.pw_uid, info.pw_gid)
    else:
        assert os.geteuid() != 0
        assert os.getegid() != 0
        preexec = os.setpgrp

    process = Popen(
        ["/bin/bash", "-c", command],
        stdin=PIPE, stdout=PIPE, stderr=PIPE,
        cwd=cwd, env=env, preexec_fn=preexec)

    def run_timeout(timeout, signal):
        try:
            output, error = process.communicate(timeout=timeout)
            output_lines = output.decode("utf8", "ignore").splitlines()
            error_lines = error.decode("utf8", "ignore").splitlines()
            return output_lines + error_lines
        except TimeoutExpired:
            os.killpg(process.pid, signal)

    # Communicate with process; send SIGTERM after timeout.
    result = run_timeout(timeout, signal.SIGTERM)

    # Try to grab output from SIGTERM; send SIGKILL after timeout.
    if result is None:
        result = run_timeout(kill_timeout, signal.SIGKILL)

    # Grab output from SIGKILL.
    # If run_timeout() returns None, the process couldn't be killed.
    if result is None:
        result = run_timeout(0, signal.SIGKILL)

    if result is None:
        print("[!] Process couldn't be killed: " + command)
    return result or []


def setid(uid, gid):
    assert uid != 0
    assert gid != 0

    def result():
        os.setgid(uid)
        os.setuid(gid)
        os.setpgrp()
    return result
