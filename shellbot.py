#!/usr/bin/env python3
# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
# Copyright (C) 2015 Nathan Krantz-Fire (https://github.com/zippynk)
# Added a command-line option for the prefix.
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
"""
Usage:
  shellbot <host> <port> [-q] [-i] [-n nick] [-m max]
           [-t timeout] [-p prefix] [-c channel]...

Options:
  -q --queries   Run commands in private queries as well as channels.
  -i --identify  Identify with NickServ. Accepts a password through stdin.
  -n nick        The nickname to use [default: shellbot].
  -m max         The maximum number of lines of output to send [default: 10].
  -t timeout     How many seconds to wait before killing processes
                 [default: 4].
  -p prefix      The prefix which identifies commands to run [default: !$].
  -c channel     An IRC channel to join.
"""
from pyrcb import IrcBot
from command import Command
from docopt import docopt
import sys
import threading


class Shellbot(IrcBot):
    def __init__(self, max_lines, timeout, prefix, allow_queries):
        super(Shellbot, self).__init__()
        self.max_lines = max_lines
        self.timeout = timeout
        self.prefix = prefix + " "
        self.allow_queries = allow_queries

    def on_message(self, message, nickname, target, is_query):
        if not message.startswith(self.prefix):
            return
        if is_query and not self.allow_queries:
            return
        print("[{0}] {1}: {2}".format(target, nickname, message))
        threading.Thread(target=self.run_command,
                         args=(message[len(self.prefix):], target)).start()

    def run_command(self, command, target):
        lines = [x for x in Command(command).run(
            self.timeout, self.timeout / 2) if x]
        for line in lines[:self.max_lines]:
            self.send(target, line)
            print(">>> " + line)
        if len(lines) > self.max_lines:
            message = "...output trimmed to {0} lines".format(self.max_lines)
            self.send(target, message)
            print(">>> " + message)
        if not lines:
            message = "Command produced no output."
            self.send(target, message)
            print(">>> " + message)


def main():
    args = docopt(__doc__)
    bot = Shellbot(int(args["-m"]), float(args["-t"]),
                   args["-p"], args["--queries"])

    bot.connect(args["<host>"], int(args["<port>"]))
    bot.register(args["-n"])

    if args["--identify"]:
        print("Password: ", end="", file=sys.stderr)
        bot.send("NickServ", "identify {0}".format(input()))

    for channel in args["-c"]:
        bot.join(channel)
    bot.listen()

if __name__ == "__main__":
    main()
