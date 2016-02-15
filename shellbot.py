#!/usr/bin/env python3
# Copyright (C) 2015-2016 taylor.fish <contact@taylor.fish>
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
  shellbot [options] <host> <port> [<channel>]...
  shellbot -h | --help | --version

Options:
  -n <nickname>    The nickname to use [default: shellbot].
  -m <max-lines>   The maximum number of lines of output to send [default: 10].
  -t <timeout>     How many seconds to wait before killing processes
                   [default: 0.25].
  -p <prefix>      The prefix which identifies commands to run [default: !$].
  -u <user>        Run commands as the specified user. Prevents the shellbot
                   process from being killed. Must be run as root.
  -d <directory>   The current working directory for all commands.
  --path           Additions to the PATH environment variable for commands.
  --queries        Allow shell commands in private queries.
  --password       Set a connection password. Can be used to identify with
                   NickServ. Uses getpass() if stdin is not a TTY.
  --getpass        Force password to be read with getpass().
  --loop           Restart if disconnected from the IRC server.
  --ssl            Use SSL/TLS to connect to the IRC server.
  --cafile <file>  Use the specified list of CA root certificates to verify
                   the IRC server's certificate. System CA certificates will
                   be used if not provided.
"""
from pyrcb import IRCBot
from command import CommandRunner
from docopt import docopt
from datetime import datetime
from getpass import getpass
import os
import re
import sys
import threading

__version__ = "0.2.4"

# If modified, replace the source URL with one to the modified version.
HELP_MESSAGE = """\
shellbot v{0}
Source: https://github.com/taylordotfish/shellbot (AGPLv3 or later)
Use in private queries is {{0}}.
To run a command, send "{{1}} <command>".
""".format(__version__)


class Shellbot(IRCBot):
    def __init__(self, lines, timeout, prefix, queries, user, cwd, **kwargs):
        super(Shellbot, self).__init__(**kwargs)
        self.max_lines = lines
        self.prefix = prefix
        self.allow_queries = queries
        self.runner = CommandRunner(timeout, cwd, user)
        self._runner_thread = threading.Thread(
            target=self.runner.loop, daemon=True)
        self._runner_thread.start()

    def on_query(self, message, nickname):
        log("[query] <{0}> {1}".format(nickname, message))
        if message.lower() == "help":
            status = ["disabled", "enabled"][self.allow_queries]
            response = HELP_MESSAGE.format(status, self.prefix)
            for line in response.splitlines():
                self.send(nickname, line)
        else:
            self.send(nickname, 'Type "help" for help.')

    def on_message(self, message, nickname, channel, is_query):
        split = message.split(" ", 1)
        if len(split) < 2 or split[0] != self.prefix:
            if is_query:
                self.on_query(message, nickname)
            return
        log("[{0}] <{1}> {2}".format(channel or "query", nickname, message))
        if is_query and not self.allow_queries:
            self.send(nickname, "Running commands in queries is disabled.")
            return
        self.runner.enqueue(split[1], self.command_done, [channel or nickname])

    def command_done(self, target, lines):
        # Remove ANSI escape codes, replace tabs, and remove blank lines.
        lines = (replace_tabs(remove_escape_codes(l)) for l in lines)
        lines = list(filter(None, lines))

        # Split long lines into multiple IRC messages
        # and then trim if there are too many.
        split_lines = []
        max_bytes = self.safe_message_length(target)
        for line in lines:
            split_lines += IRCBot.split_string(line, max_bytes)

        logged_lines = []
        for line in split_lines[:self.max_lines]:
            self.send(target, line)
            logged_lines.append(line)
        if len(lines) > self.max_lines:
            message = "...output trimmed to {0} lines.".format(self.max_lines)
            self.send(target, message)
            logged_lines.append(message)
        if not lines:
            message = "Command produced no output."
            self.send(target, message)
            logged_lines.append(message)

        for line in logged_lines:
            log("[{0}] >>> {1}".format(target, line))


def remove_escape_codes(string):
    return re.sub(r"\x1b.*?[a-zA-Z]", "", string)


def replace_tabs(string):
    result = ""
    split = string.split("\t")
    for s in split[:-1]:
        result += s + " " * (8 - (len(s) % 8))
    return result + split[-1]


def stderr(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)


def log(*args, **kwargs):
    print(datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"), *args, **kwargs)


def start(bot, args, password):
    bot.connect(
        args["<host>"], int(args["<port>"]),
        use_ssl=args["--ssl"], ca_certs=args["--cafile"])
    if password:
        bot.password(password)
    bot.register(args["-n"])
    for channel in args["<channel>"]:
        bot.join(channel)
    bot.listen()
    bot.runner.reset()
    print("Disconnected from server.")


def main():
    args = docopt(__doc__, version=__version__)
    if args["-u"] and os.geteuid() != 0:
        stderr('Must be run as root with "-u".')
        return
    if not args["-u"] and os.geteuid() == 0:
        stderr('WARNING: Running as root without "-u".')

    password = None
    if args["--password"]:
        stderr("Password: ", end="", flush=True)
        use_getpass = sys.stdin.isatty() or args["--getpass"]
        password = getpass("") if use_getpass else input()
        if not use_getpass:
            stderr("Received password.")

    bot = Shellbot(
        lines=int(args["-m"]), timeout=float(args["-t"]), prefix=args["-p"],
        queries=args["--queries"], user=args["-u"], cwd=args["-d"])
    if args["--path"]:
        bot.runner.path += ":" + args["--path"]

    start(bot, args, password)
    while args["--loop"]:
        start(bot, args, password)


if __name__ == "__main__":
    main()
