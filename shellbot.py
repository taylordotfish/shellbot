#!/usr/bin/env python3
# Copyright (C) 2015 taylor.fish (https://github.com/taylordotfish)
# Copyright (C) 2015 nc Krantz-Fire (https://pineco.net/)
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
#
# See EXCEPTIONS for additional permissions.
"""
Usage:
  shellbot <host> <port> [options] [-c <channel>]...
  shellbot -h | --help

Options:
  -h --help       Display this help message.
  -q --queries    Run commands in private queries as well as channels.
  -i --identify   Identify with NickServ. Accepts a password through stdin.
  -n <nickname>   The nickname to use [default: shellbot].
  -c <channel>    An IRC channel to join.
  -m <max-lines>  The maximum number of lines of output to send [default: 10].
  -t <timeout>    How many seconds to wait before killing processes
  -p <prefix>     The prefix which identifies commands to run [default: !$].
  -u <user>       Run commands as the specified user. Prevents the shellbot
                  process from being killed. Must be run as root.
  -d <directory>  The current working directory for all commands.
                  [default: 4].
"""
from pyrcb import IrcBot
from command import run_shell
from docopt import docopt
from datetime import datetime
import os
import re
import sys
import threading

# If modified, replace the source URL with one to the modified version.
help_message = """\
Source: https://github.com/taylordotfish/shellbot (AGPLv3 or later)
Use in private queries is {0}.
To run a command, send "{1} [command]".
"""


class Shellbot(IrcBot):
    def __init__(self, max_lines, timeout, prefix, queries, user, cwd):
        super(Shellbot, self).__init__()
        self.max_lines = max_lines
        self.timeout = timeout
        self.prefix = prefix + " "
        self.allow_queries = queries
        self.cmd_user = user
        self.cwd = cwd

    def on_query(self, message, nickname):
        if message.lower() == "help":
            help_lines = help_message.format(
                ["disabled", "enabled"][self.allow_queries],
                self.prefix).splitlines()
            for line in help_lines:
                self.send(nickname, line)
        else:
            self.send(nickname, '"/msg {0} help" for help'
                                .format(self.nickname))

    def on_message(self, message, nickname, target, is_query):
        if not message.startswith(self.prefix):
            if is_query:
                self.on_query(message, nickname)
            return
        if is_query and not self.allow_queries:
            self.send(nickname, "Use in private queries is disabled.")
            return
        print("[{3}] [{0}] <{1}> {2}".format(
            target, nickname, message, datetime.now().replace(microsecond=0)))
        threading.Thread(target=self.run_command,
                         args=(message[len(self.prefix):], target)).start()

    def run_command(self, command, target):
        # Strip ANSI escape sequences.
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
        print("Received password.", file=sys.stderr)
    bot.register(args["-n"])

    for channel in args["-c"]:
        bot.join(channel)
    bot.listen()

if __name__ == "__main__":
    main()
