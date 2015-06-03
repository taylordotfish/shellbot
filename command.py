# Copyright (C) 2015 taylor.fish (https://github.com/taylordotfish)
#
# This file is part of shellbot.
#
# shellbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# shellbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with shellbot.  If not, see <http://www.gnu.org/licenses/>.

from subprocess import call, Popen, PIPE, TimeoutExpired
import os
import signal
import threading


def run_shell(command, sys_user, timeout, term_timeout):
    sudo_wrapper = ["/usr/bin/sudo", "-Hiu", sys_user] if sys_user else []
    process = Popen(
        sudo_wrapper + ["/bin/bash", "-c", command],
        stdin=PIPE, stdout=PIPE, stderr=PIPE,
        universal_newlines=True, preexec_fn=os.setpgrp)

    def run_timeout(timeout, signal):
        try:
            output, error = process.communicate(timeout=timeout)
            return output.splitlines() + error.splitlines()
        except TimeoutExpired:
            call(sudo_wrapper + ["/bin/kill", "-" + str(signal), "-" + str(process.pid)])

    result = run_timeout(timeout, signal.SIGTERM)
    if result is None:
        result = run_timeout(term_timeout, signal.SIGKILL)
    return result
