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

from subprocess import call, Popen, PIPE, TimeoutExpired
import os
import pwd
import signal
import threading

env = {"PATH": "/bin:/usr/bin:/usr/games:/usr/local/bin:/usr/local/games"}


def run_shell(command, user, cwd, timeout, term_timeout):
    if user:
        info = pwd.getpwnam(user)
        preexec = setid(info.pw_uid, info.pw_gid)
    else:
        assert os.geteuid() != 0
        assert os.getegid() != 0
        preexec = os.setpgrp

    process = Popen(
        ["/bin/bash", "-c", command],
        stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=cwd, env=env,
        universal_newlines=True, preexec_fn=preexec)

    def run_timeout(timeout, signal):
        try:
            output, error = process.communicate(timeout=timeout)
            return output.splitlines() + error.splitlines()
        except TimeoutExpired:
            os.killpg(process.pid, signal)

    result = run_timeout(timeout, signal.SIGTERM)
    for i in range(2):
        if result is None:
            result = run_timeout(term_timeout, signal.SIGKILL)
    return result


def setid(uid, gid):
    assert uid != 0
    assert gid != 0

    def result():
        os.setgid(uid)
        os.setuid(gid)
        os.setpgrp()
    return result
