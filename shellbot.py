#!/usr/bin/env python3
# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
# Copyright (C) 2015 Nathan Krantz-Fire (https://github.com/zippynk)
# Added --prefix option.
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
"""
Usage:
  shellbot <host> <port> [-u user] [-d directory] [-q] [-i]
           [-n nick] [-m max] [-t timeout] [-p prefix] [-c channel]...

Options:
  -u user        Run commands as the specified user. Prevents the shellbot
                 process from being killed. Must be run as root.
  -d directory   The current working directory for all commands.
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
from command import run_shell
from docopt import docopt
import os
import re
import sys
import threading


class Shellbot(IrcBot):
    def __init__(self, max_lines, timeout, prefix, queries, user, cwd):
        super(Shellbot, self).__init__()
        self.max_lines = max_lines
        self.timeout = timeout
        self.prefix = prefix + " "
        self.allow_queries = queries
        self.cmd_user = user
        self.cwd = cwd

    def on_message(self, message, nickname, target, is_query):
        if not message.startswith(self.prefix):
            return
        if is_query and not self.allow_queries:
            return
        print("[{0}] <{1}> {2}".format(target, nickname, message))
        threading.Thread(target=self.run_command,
                         args=(message[len(self.prefix):], target)).start()

    def run_command(self, command, target):
        lines = [re.sub(r"\x1b.*?[a-zA-Z]", "", l) for l in run_shell(
            command, self.cmd_user, self.cwd, self.timeout, self.timeout / 2)]
        lines = [l for l in lines if l]

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
    if args["-u"] and os.geteuid() != 0:
        print('Must be run as root when "-u" is specified.')
        return
    if not args["-u"] and os.geteuid() == 0:
        print('Cannot be run as root unless "-u" is specified.')
        return

    bot = Shellbot(int(args["-m"]), float(args["-t"]), args["-p"],
                   args["--queries"], args["-u"], args["-d"])
    bot.connect(args["<host>"], int(args["<port>"]))

    if args["--identify"]:
        print("Password: ", end="", file=sys.stderr)
        bot.password(input())
    bot.register(args["-n"])

    for channel in args["-c"]:
        bot.join(channel)
    bot.listen()

if __name__ == "__main__":
    main()
