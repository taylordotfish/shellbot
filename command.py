# Copyright (C) 2015 taylor.fish (https://github.com/taylordotfish)
# 
# This file is part of Shellbot.
# 
# Shellbot is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Shellbot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Shellbot.  If not, see <http://www.gnu.org/licenses/>.
from subprocess import Popen, PIPE
import threading


class Command():
    def __init__(self, command):
        self.command = command
        self.process = None
        self.output = ""
        self.error = ""

    def run(self, timeout, term_timeout):
        def start_process():
            self.process = Popen(self.command, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, universal_newlines=True)
            self.output, self.error = self.process.communicate()

        thread = threading.Thread(target=start_process)
        thread.start()
        thread.join(timeout)

        if thread.is_alive():
            self.process.terminate(term_timeout)
            thread.join(term_timeout)
        if thread.is_alive():
            self.process.kill()
            thread.join()
        return self.output.splitlines() + self.error.splitlines()
