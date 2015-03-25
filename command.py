# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
# 
# This file is part of Shellbot.
# 
# Shellbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Shellbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Shellbot.  If not, see <http://www.gnu.org/licenses/>.
from subprocess import Popen, PIPE
import threading
import os
import signal


class Command():
    def __init__(self, command):
        self.command = command
        self.process = None
        self.output = ""
        self.error = ""

    def run(self, timeout, term_timeout):
        def start_process():
            self.process = Popen(["/bin/bash", "-c", self.command],
                stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True,
                start_new_session=True)
            self.output, self.error = self.process.communicate()

        thread = threading.Thread(target=start_process)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            os.killpg(self.process.pid, signal.SIGTERM)
            thread.join(term_timeout)
        if thread.is_alive():
            os.killpg(self.process.pid, signal.SIGKILL)
            thread.join()
        return self.output.splitlines() + self.error.splitlines()
