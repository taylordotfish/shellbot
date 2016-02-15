# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 taylor.fish <contact@taylor.fish>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from __future__ import unicode_literals
from bisect import insort
from collections import OrderedDict
from locale import getpreferredencoding
import errno
import inspect
import re
import socket
import ssl
import sys
import threading
import time

__version__ = "1.9.0"

# ustr is unicode in Python 2 (because of unicode_literals)
# and str in Python 3.
ustr = type("")

# Use time.monotonic() if available (Python >= 3.3) to avoid problems with
# system time changes and leap seconds.
best_clock = getattr(time, "monotonic", time.time)


class IRCBot(object):
    """The base class for IRC bots. IRC bots should inherit from this class and
    override any events they wish to handle.

    Instances of this class are reusable.

    :param bool debug_print: Whether or not communication with the IRC server
      should be printed for debugging/logging purposes.
    :param callable print_function: An optional function to be used with
      ``debug_print``. Should accept a single unicode string argument.
      If not provided, communication is printed to stdout.
    :param bool delay: Whether or not sent messages should be delayed to avoid
      server throttling or spam prevention. See :ref:`delay-options`.
    """
    def __init__(self, debug_print=False, print_function=None, delay=True):
        self.debug_print = debug_print
        self.print_function = print_function or safe_print
        self.delay = delay
        self.events = IDefaultDict(list)

        # Multiplied by the number of consecutive messages sent to determine
        # how many seconds to wait before sending the next one.
        self.delay_multiplier = 0.1

        # The maximum number of seconds to wait before sending a message.
        self.max_delay = 1.5

        # How many seconds must pass before a message is not considered
        # consecutive.
        self.consecutive_timeout = 5

        self._first_use = True
        self._init_attributes()
        self._register_events()

    # Initializes attributes.
    def _init_attributes(self):
        self._buffer = ""
        self.socket = socket.socket()
        self.hostname = None
        self.port = None

        self.alive = False
        self.is_registered = False
        self.nickname = None
        self.channels = []

        self._names_buffer = IDefaultDict(list)
        self.old_nicklist = IDefaultDict(list)
        self.nicklist = IDefaultDict(list)

        # Buffer of delayed messages. Stores tuples of the time
        # to be sent and the message text.
        self._delay_buffer = []

        # Maps a channel/nickname to the time of the most recent message
        # sent and how many consecutive messages have been sent.
        self.last_sent = IDefaultDict(lambda: (0, 0))
        self.delay_event = threading.Event()
        self.listen_event = threading.Event()

    # Registers event handlers.
    def _register_events(self):
        self.register_event(self._on_001_welcome, "001")
        self.register_event(self._on_ping, "PING")
        self.register_event(self._on_join, "JOIN")
        self.register_event(self._on_part, "PART")
        self.register_event(self._on_quit, "QUIT")
        self.register_event(self._on_kick, "KICK")
        self.register_event(self._on_nick, "NICK")
        self.register_event(self._on_message, "PRIVMSG")
        self.register_event(self._on_notice, "NOTICE")
        self.register_event(self._on_353_namreply, "353")
        self.register_event(self._on_366_endofnames, "366")
        self.register_event(self._on_433_nicknameinuse, "433")

    # ============
    # IRC commands
    # ============

    def password(self, password):
        """Sets a connection password. (``PASS`` command)

        This method can be used to identify with NickServ.

        :param str password: The password to use. A password in the format
          ``nickname:password`` can be provided to identify as a nickname other
          than the one being used.
        """
        self.send_raw("PASS", [password])

    def register(self, nickname, realname=None):
        """Registers with the server. (``USER`` and ``NICK`` commands.)

        :param str nickname: The nickname to use. A `ValueError` is raised if
          the nickname is already in use.
        :param str realname: The real name to use. If not specified,
          ``nickname`` will be used.
        """
        self.nickname = IStr(nickname)
        self.send_raw("USER", [nickname, "8", "*", realname or nickname])
        self.send_raw("NICK", [nickname])
        while not self.is_registered:
            line = self.readline()
            if line is None:
                raise IOError("Lost connection to the server.")
            self._handle(line)

    def join(self, channel):
        """Joins a channel. (``JOIN`` command)

        :param str channel: The channel to join. Must start with the channel
          prefix.
        """
        self.send_raw("JOIN", [channel])

    def part(self, channel, message=None):
        """Leaves a channel. (``PART`` command)

        :param str channel: The channel to leave. Must start with the channel
          prefix.
        :param str message: An optional part message.
        """
        self.send_raw("PART", filter(None, [channel, message]))

    def quit(self, message=None):
        """Disconnects from the server. (``QUIT`` command)

        :param str message: An optional quit message.
        """
        try:
            self.send_raw("QUIT", filter(None, [message]))
        finally:
            self.close_socket()

    def send(self, target, message, split=True, nobreak=True):
        """Sends a message to a channel or user. (``PRIVMSG`` command)

        :param str target: The recipient of the message (either a channel or a
          nickname).
        :param str message: The message to send.
        :param bool split: If true, long messages will be split into multiple
          pieces to avoid truncation. See :meth:`IRCBot.split_string`.
        :param bool nobreak: If true (and ``split`` is true), long messages
          will be split only where whitespace occurs to avoid breaking words,
          unless this is not possible.
        """
        self._privmsg_or_notice(
            target, message, split, nobreak, notice=False)

    def send_notice(self, target, message, split=True, nobreak=True):
        """Sends a notice to a channel or user. (``NOTICE`` command)

        :param str target: The recipient of the notice (either a channel or a
          nickname).
        :param str notice: The notice to send.
        :param bool split: If true, long messages will be split into multiple
          pieces to avoid truncation. See :meth:`IRCBot.split_string`.
        :param bool nobreak: If true (and ``split`` is true), long messages
          will be split only where whitespace occurs to avoid breaking words,
          unless this is not possible.
        """
        self._privmsg_or_notice(
            target, message, split, nobreak, notice=True)

    def nick(self, new_nickname):
        """Changes the bot's nickname. (``NICK`` command)

        :param str new_nickname: The bot's new nickname.
        """
        self.send_raw("NICK", [new_nickname])

    def names(self, channel):
        """Requests a list of users in a channel. (``NAMES`` command)

        Calling this method is usually unnecessary because bots automatically
        keep track of users in joined channels. See `IRCBot.nicklist`.

        :param str channel: The channel to request a list of users from.
        """
        if channel and not channel.isspace():
            self.send_raw("NAMES", [channel])

    def send_raw(self, command, args=[]):
        """Sends a raw IRC message.

        :param str command: The command to send.
        :param list args: A list of arguments to the command.
        """
        self.writeline(IRCBot.format(command, args))

    def _privmsg_or_notice(self, target, message, split, nobreak, notice):
        messages = [message]
        if split:
            bytelen = self.safe_message_length(target, notice=notice)
            try:
                messages = IRCBot.split_string(message, bytelen, nobreak)
            except ValueError:
                pass
        command = ["PRIVMSG", "NOTICE"][notice]
        for msg in messages:
            self.add_delayed(target, command, [target, msg])

    # ==================
    # IRC event handlers
    # ==================

    def _on_001_welcome(self, server, nickname, *args):
        self.nickname = IStr(nickname)
        self.is_registered = True

    def _on_ping(self, *args):
        self.send_raw("PONG", args[1:])

    def _on_join(self, nickname, channel):
        self.add_nickname(nickname, [channel])
        self.on_join(nickname, IStr(channel))

    def _on_part(self, nickname, channel, message):
        self.remove_nickname(nickname, [channel])
        self.on_part(nickname, IStr(channel), message)

    def _on_quit(self, nickname, message):
        channels = self.remove_nickname(nickname, self.channels)
        self.on_quit(nickname, message, channels)

    def _on_kick(self, nickname, channel, target, message):
        self.remove_nickname(target, [channel])
        self.on_kick(nickname, IStr(channel), IStr(target), message)

    def _on_message(self, nickname, target, message):
        is_query = (target == self.nickname)
        channel = None if is_query else IStr(target)
        self.on_message(message, nickname, channel, is_query)

    def _on_notice(self, nickname, target, message):
        is_query = (target == self.nickname)
        channel = None if is_query else IStr(target)
        self.on_notice(message, nickname, channel, is_query)

    def _on_nick(self, nickname, new_nickname):
        self.replace_nickname(nickname, new_nickname)
        self.on_nick(nickname, new_nickname)

    def _on_353_namreply(self, server, target, chan_type, channel, names):
        names = [IStr(n.lstrip("@+")) for n in names.split()]
        self._names_buffer[channel] += names

    def _on_366_endofnames(self, server, target, channel, *args):
        self.nicklist.update(self._names_buffer)
        for chan, names in self._names_buffer.items():
            self.on_names(chan, names)
        if channel not in self._names_buffer:
            self.on_names(IStr(channel), [])
        self._names_buffer.clear()

    def _on_433_nicknameinuse(self, *args):
        if not self.is_registered:
            raise ValueError("Nickname is already in use.")

    def on_join(self, nickname, channel):
        """Called when a user joins a channel. (``JOIN`` command)

        :param Nickname nickname: The nickname of the user.
        :param IStr channel: The channel being joined.
        """

    def on_part(self, nickname, channel, message):
        """Called when a user leaves a channel. (``PART`` command)

        :param Nickname nickname: The nickname of the user.
        :param IStr channel: The channel being left.
        :param str message: The part message.
        """

    def on_quit(self, nickname, message, channels):
        """Called when a user disconnects from the server. (``QUIT`` command)

        :param Nickname nickname: The nickname of the user.
        :param str message: The quit message.
        :param list channels: A list of channels the user was in.
        """

    def on_kick(self, nickname, channel, target, message):
        """Called when a user is kicked from a channel. (``KICK`` command)

        :param Nickname nickname: The nickname of the user that is kicking
          someone.
        :param IStr channel: The channel someone is being kicked from.
        :param IStr target: The nickname of the user being kicked. Check if
          this is equal to ``self.nickname`` to check if this bot was kicked.
        :param str message: The kick message.
        """

    def on_message(self, message, nickname, channel, is_query):
        """Called when a message is received. (``PRIVMSG`` command)

        :param str message: The text of the message.
        :param Nickname nickname: The nickname of the user that sent the
          message.
        :param IStr channel: The channel the message is in. If sent in a
          private query, this is `None`.
        :param bool is_query: Whether or not the message was sent to this bot
          in a private query.
        """

    def on_notice(self, message, nickname, channel, is_query):
        """Called when a notice is received. (``NOTICE`` command)

        :param str message: The text of the notice.
        :param Nickname nickname: The nickname of the user that sent the
          notice.
        :param IStr channel: The channel the notice is in. If sent in a private
          query, this is `None`.
        :param bool is_query: Whether or not the notice was sent to this bot in
          a private query.
        """

    def on_nick(self, nickname, new_nickname):
        """Called when a user changes nicknames. (``NICK`` command)

        :param Nickname nickname: The user's old nickname.
        :param IStr new_nickname: The user's new nickname.
        """

    def on_names(self, channel, names):
        """Called when a list of users in a channel is received.

        :param IStr channel: The channel that the list of users describes.
        :param list names: A list of nicknames of users in the channel.
          Nicknames are of type `IStr`.
        """

    def on_raw(self, nickname, command, args):
        """Called when any IRC message is received. It is usually better to use
        :meth:`~IRCBot.register_event` instead of this method.

        :param Nickname nickname: The nickname of the user (or the server in
          some cases) that sent the message.
        :param IStr command: The command (or numeric reply) received.
        :param list args: A list of arguments to the command. Arguments are of
          type `str`.
        """

    # ====================
    # Other public methods
    # ====================

    def connect(self, hostname, port, use_ssl=False, ca_certs=None,
                verify_ssl=True):
        """Connects to an IRC server.

        SSL/TLS support requires at least Python 3.2 or Python 2.7.9. On
        Windows, system CA certificates cannot be loaded with Python 3.2 or
        3.3, so either ``ca_certs`` must be provided or ``verify_ssl`` must be
        false.

        :param str hostname: The hostname of the IRC server.
        :param int port: The port of the IRC server.
        :param bool use_ssl: Whether or not to use SSL/TLS.
        :param str ca_certs: Optional path to a list of trusted CA
          certificates. If omitted, the system's default CA certificates will
          be loaded instead.
        :param bool verify_ssl: Whether or not to verify the server's SSL/TLS
          certificate and hostname.
        """
        if not self._first_use:
            self._init_attributes()
        self._first_use = False

        self.hostname = hostname
        self.port = port
        self.socket.connect((hostname, port))

        if use_ssl:
            self.socket = wrap_socket(
                self.socket, hostname, ca_certs, verify_ssl)

        self.alive = True
        if self.delay:
            t = threading.Thread(target=self.delay_loop)
            t.daemon = True
            t.start()

    def listen(self):
        """Listens for incoming messages and calls the appropriate events.

        This method is blocking. Either this method or :meth:`listen_async`
        should be called after registering and joining channels.
        """
        try:
            self._listen()
        finally:
            self.close_socket()
            self.listen_event.set()

    def listen_async(self, callback=None):
        """Listens for incoming messages on a separate thread and calls the
        appropriate events.

        This method is non-blocking. Either this method of :meth:`listen`
        should be called after registering and joining channels.

        :param callable callback: An optional function to call when connection
          to the server is lost.
        """
        def target():
            try:
                self._listen()
            finally:
                self.close_socket()
                if callback:
                    callback()
                self.listen_event.set()

        t = threading.Thread(target=target)
        t.daemon = True
        t.start()

    def wait(self, timeout=None):
        """Blocks until connection to the server is lost, or until the
        operation times out if a timeout is given.

        This can be useful with :meth:`listen_async` to keep the program alive
        if there is nothing more to do on the main thread.

        Using this function with a ``timeout`` parameter is a better
        alternative to :func:`time.sleep`, since it will return as soon as the
        bot loses connection, so the program can respond appropriately or end.

        :param float timeout: A timeout for the operation in seconds.
        :returns: `True` if the method returned because the bot lost connection
          or `False` if the operation timed out.
        """
        return self.listen_event.wait(timeout)

    def register_event(self, function, command):
        """Registers an event handler for an IRC command or numeric reply.

        ``function`` should be an instance method of an IRCBot subclass. Its
        signature should be as follows::

            function(self, nickname[, arg1, arg2, arg3...])

        ``nickname`` (type `Nickname`, a subclass of `IStr`) is the nickname of
        the user from whom the IRC message/command originated. When handling
        numeric replies, it may be more appropriate to name this parameter
        "server".

        Optional parameters after ``nickname`` represent arguments to the IRC
        command. These are of type `str`, not `IStr`, so if any of the
        parameters represent channels or nicknames, they should be converted to
        `IStr`.

        If the number of IRC arguments received is less than the number
        ``function`` accepts, the remaining function arguments will be set to
        `None`.  This ensures that IRC commands with an optional last argument
        will be handled correctly.

        Multiple events can be registered for the same IRC command, but is
        usually isn't necessary to do this.

        :param callable function: The event handler.
        :param str command: The IRC command or numeric reply to listen for.
        """
        nargs = get_required_args(function)
        self.events[command].append((function, nargs))

    def safe_message_length(self, target, notice=False):
        """Gets the maximum number of bytes the text of an IRC PRIVMSG (or
        optionally a NOTICE) can be without the message possibly being cut off
        due to the 512-byte IRC message limit. This method accounts for extra
        information added by the IRC server.

        You will most likely want to use the value returned by this function
        with :meth:`IRCBot.split_string`.

        However, it is often not necessary to use this method;
        :meth:`~IRCBot.send` and :meth:`~IRCBot.send_notice` automatically
        split messages if they're too long.

        :param str target: The channel or nickname the PRIVMSG will be sent to.
        :param bool notice: If true, the calculation will be performed for an
          IRC NOTICE, instead of a PRIVMSG.
        """
        return self.safe_length(["PRIVMSG", "NOTICE"][notice], target)

    # ==============
    # Static methods
    # ==============

    @staticmethod
    def split_string(string, bytelen, nobreak=True, once=False):
        """Splits a string into pieces that will take up no more than the
        specified number of bytes when encoded as UTF-8.

        IRC messages are limited to 512 bytes, so sometimes it is necessary to
        split longer messages. This method splits strings based on how many
        bytes, rather than characters, they take up, keeping multi-byte
        characters intact. For example::

            >>> IRCBot.split_string("This is a test§§§§", 8)
            ["This is", "a", "test§§", "§§"]
            >>> IRCBot.split_string("This is a test§§§§", 8, whitespace=False)
            ["This is ", "a test§", "§§§"]
            >>> IRCBot.split_string("This is a test§§§§", 8, once=True)
            ["This is", "a test§§§§"]

        You can use :meth:`~IRCBot.safe_message_length` and
        :meth:`~IRCBot.safe_notice_length` to determine how large each string
        piece should be.

        However, it is often not necessary to call this method because
        :meth:`~IRCBot.send` and :meth:`~IRCBot.send_notice` both split long
        messages by default.

        :param str string: The string to split.
        :param int bytelen: The maximum number of bytes string pieces should
          take up when encoded as UTF-8.
        :param bool nobreak: If true, strings will be split only where
          whitespace occurs to avoid breaking words, unless this is not
          possible. If present, one space character will be removed between
          string pieces.
        :param bool once: If true, the string will only be split once. The
          second piece is not guaranteed to be less than ``bytelen``.
        :returns: A list of the split string pieces.
        """
        result = []
        rest = string
        split_func = IRCBot.split_nobreak if nobreak else IRCBot.split_once
        while not result or (rest and not once):
            split, rest = split_func(rest, bytelen)
            result.append(split)
        return result

    # Splits a string based on the number of bytes it takes
    # up when encoded as UTF-8.
    @staticmethod
    def split_once(string, bytelen):
        if bytelen <= 0:
            raise ValueError("Number of bytes must be positive.")
        bytestr = string.encode("utf8")
        if len(bytestr) <= bytelen:
            return (string, "")
        split, rest = bytestr[:bytelen], bytestr[bytelen:]
        # If the last byte of "split" is non-ASCII and the first byte of "rest"
        # is neither ASCII nor the start of a multi-byte character, then a
        # multi-byte Unicode character has been split and needs to be fixed.
        if ord(split[-1:]) >= 0x80 and 0x80 <= ord(rest[:1]) <= 0xc0:
            chars = reversed(list(enumerate(split)))
            start = next(i for i, c in chars if c >= 0xc0)
            split, rest = split[:start], split[start:] + rest
        return (split.decode("utf8"), rest.decode("utf8"))

    # Like split_once(), but splits only where whitespace occurs to avoid
    # breaking words (unless not possible). If present, once space character
    # between split strings will be removed (similar to WeeChat's behavior).
    @staticmethod
    def split_nobreak(string, bytelen):
        split, rest = IRCBot.split_once(string, bytelen)
        if not rest:
            return (split, rest)
        if not split[-1].isspace() and not rest[0].isspace():
            chars = reversed(list(enumerate(split)))
            space = next((i for i, c in chars if c.isspace()), -1)
            if space >= 0:
                split, rest = split[:space], split[space:] + rest
        # If present, remove one space character between strings.
        if rest[0] == " ":
            rest = rest[1:]
        elif split[-1] == " ":
            split = split[:-1]
        return (split, rest)

    # Parses an IRC message.
    @staticmethod
    def parse(message):
        # Regex to parse IRC messages.
        match = re.match(r"""
            (?::  # Start of prefix
              (.*?)(?:  # Nickname
                (?:!(.*?))?  # User
                @(.*?)  # Host
              )?[ ]
            )?
            ([^ ]+)  # Command
            ((?:\ [^: ][^ ]*){0,14})  # Arguments
            (?:\ :?(.*))?  # Trailing argument
            """, message, re.VERBOSE)
        nick, user, host, cmd, args, trailing = match.groups("")
        nick = Nickname(nick, username=user, hostname=host)
        cmd = IStr(cmd)
        args = args.split()
        if trailing:
            args.append(trailing)
        return (nick, cmd, args)

    # Formats an IRC message.
    @staticmethod
    def format(command, args=[]):
        command = ustr(command)
        args = list(map(ustr, args))
        if not all(args + [command]):
            raise ValueError("Command/args may not be empty strings.")
        if not re.match(r"^[a-zA-Z0-9]+$", command):
            raise ValueError("Command must be alphanumeric.")
        if not all(re.match(r"^[^\0\r\n]+$", arg) for arg in args):
            raise ValueError(r"Arguments may not contain [\0\r\n].")
        if any(arg[0] == ":" for arg in args[:-1]):
            raise ValueError("Only the last argument may start with ':'.")
        if any(" " in arg for arg in args[:-1]):
            raise ValueError("Only the last argument may contain ' '.")
        if args:
            args[-1] = ":" + args[-1]
        return " ".join([command] + args)

    # ===============
    # Private methods
    # ===============

    # Method which actually listens for incoming messages.
    # Wrapped in a try-finally clause in the public method listen().
    def _listen(self):
        while True:
            try:
                line = self.readline()
            except socket.error as e:
                if not catch_socket_error(e):
                    raise
                return
            if line is None:
                return
            self._handle(line)

    # Parses an IRC message and calls the appropriate events.
    def _handle(self, message):
        nickname, command, args = IRCBot.parse(message)
        for handler, nargs in self.events.get(command, []):
            handler_args = [nickname] + args

            # Fill in any extra arguments with None.
            if len(handler_args) < nargs:
                handler_args += [None] * (nargs - len(handler_args))
            handler(*handler_args)
        self.on_raw(nickname, command, args)

    # Adds a nickname to channels' nicklists and adds channels
    # to the list of channels if this bot is being added.
    def add_nickname(self, nickname, channels):
        for channel in channels:
            if nickname == self.nickname:
                self.channels.append(IStr(channel))
            self.nicklist[channel].append(IStr(nickname))

    # Removes a nickname from channels' nicklists and removes channels
    # from the list of channels if this bot is being removed.
    def remove_nickname(self, nickname, channels):
        removed_channels = []
        pairs = [(c, self.nicklist[c]) for c in channels]
        pairs = [(c, n) for c, n in pairs if nickname in n]
        for channel, nicklist in pairs:
            if nickname == self.nickname and channel in self.channels:
                self.channels.remove(channel)
            nicklist.remove(nickname)
            removed_channels.append(channel)
        return removed_channels

    # Replaces a nickname in all joined channels' nicklists.
    def replace_nickname(self, nickname, new_nickname):
        for channel in self.channels:
            if nickname == self.nickname:
                self.nickname = new_nickname
            nicklist = self.nicklist[channel]
            if nickname in nicklist:
                nicklist.remove(nickname)
                nicklist.append(IStr(new_nickname))

    def safe_length(self, *args):
        # :<nickname>!<user>@<host>
        # <user> commonly has a 10-character maximum
        # <host> is 63 characters maximum
        mask = len(":" + self.nickname + "!") + 10 + len("@") + 63
        msg = mask + len(" " + " ".join(args) + " :\r\n")
        # IRC messages are limited to 512 characters.
        return 512 - msg

    # Adds a delayed message, or sends the message if delays are off.
    def add_delayed(self, target, command, args):
        if not self.delay:
            self.send_raw(command, args)
            return

        last_time, consecutive = self.last_sent[target]
        last_delta = best_clock() - last_time
        if last_delta >= self.consecutive_timeout:
            consecutive = 0

        delay = min(consecutive * self.delay_multiplier, self.max_delay)
        message_time = max(last_time, best_clock()) + delay
        self.last_sent[target] = (message_time, consecutive + 1)

        insort(self._delay_buffer, (message_time, (command, args)))
        self.delay_event.set()

    # Sends delayed messages at the appropriate time.
    def delay_loop(self):
        while self.alive:
            self.delay_event.clear()
            if any(self._delay_buffer):
                # Get the oldest message.
                message_time, (command, args) = self._delay_buffer[0]
                delay = message_time - best_clock()

                # If there is no delay or the program finishes
                # waiting for the delay, send the message.
                if delay <= 0 or not self.delay_event.wait(timeout=delay):
                    self.send_raw(command, args)
                    del self._delay_buffer[0]
            else:
                self.delay_event.wait()

    # Reads a line from the socket.
    def readline(self):
        while "\r\n" not in self._buffer:
            data = self.socket.recv(1024)
            if not data:
                return
            self._buffer += data.decode("utf8", "ignore")

        line, self._buffer = self._buffer.split("\r\n", 1)
        if self.debug_print:
            self.print_function(line)
        return line

    # Writes a line to the socket.
    def writeline(self, data):
        self.socket.sendall((data + "\r\n").encode("utf8", "ignore"))
        if self.debug_print:
            self.print_function(">>> " + data)

    # Closes the socket.
    def close_socket(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except socket.error as e:
            if not catch_socket_error(e):
                raise
        finally:
            self.alive = False
            self.delay_event.set()


# Gets the number of required positional arguments of a function.
# Does not include the "self" parameter for bound methods.
def get_required_args(func):
    result = 0
    if hasattr(inspect, "signature"):
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            is_positional = param.kind in [
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD]
            no_default = param.default is inspect.Parameter.empty
            if is_positional and no_default:
                result += 1
        return result
    spec = getattr(inspect, "getfullargspec", inspect.getargspec)(func)
    result = len(spec.args) - len(spec.defaults or [])
    # Don't include the "self" parameter for bound methods.
    if hasattr(func, "__self__"):
        result -= 1
    return result


# Wraps a plain socket into an SSL one. Attempts to load default CA
# certificates if none are provided. Verifies the server's certificate and
# hostname if specified.
def wrap_socket(sock, hostname=None, ca_certs=None, verify_ssl=True):
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    # Use load_default_certs() if available (Python >= 3.4); otherwise, use
    # set_default_verify_paths() (doesn't work on Windows).
    load_default_certs = getattr(
        context, "load_default_certs", context.set_default_verify_paths)

    if verify_ssl:
        context.verify_mode = ssl.CERT_REQUIRED
    if ca_certs:
        context.load_verify_locations(cafile=ca_certs)
    else:
        load_default_certs()

    sock = context.wrap_socket(sock)
    if verify_ssl:
        ssl.match_hostname(sock.getpeercert(), hostname)
    return sock


# Checks if a socket exception should be caught by looking at its errno.
def catch_socket_error(ex):
    return ex.errno in [
        errno.EPIPE,  # Broken pipe
        errno.EBADF,  # Bad file descriptor; close() has been called
        errno.ENOTCONN,  # Transport endpoint not connected
        errno.ESHUTDOWN,  # Can't send after shutdown
        errno.ECONNABORTED,  # Connection aborted
        errno.ECONNRESET,  # Connection reset
        errno.ECONNREFUSED,  # Connection refused
    ]


# Prints a string, replacing characters invalid in the current encoding.
def safe_print(string, file=sys.stdout):
    encoding = getpreferredencoding()
    print(string.encode(encoding, "replace").decode(encoding), file=file)


# Decorator to implement case-insensitive methods for IStr.
def istr_methods(cls):
    def get_method(name):
        def method(self, string, *args, **kwargs):
            if isinstance(string, (str, type(""))):
                string = IStr.make_lower(string)
            return getattr(self._lower, name)(string, *args, **kwargs)
        return method

    for name in ["index", "find", "count", "startswith", "endswith"]:
        setattr(cls, name, get_method(name))
    for name in ["lt", "le", "ne", "eq", "gt", "ge", "contains"]:
        name = "__{0}__".format(name)
        setattr(cls, name, get_method(name))
    return cls


# Decorator to implement case-insensitive methods for IDefaultDict.
def idefaultdict_methods(cls):
    def get_method(name):
        def method(self, key, *args, **kwargs):
            if isinstance(key, (str, type(""))):
                key = IStr(key)
            return getattr(super(cls, self), name)(key, *args, **kwargs)
        return method

    for name in ["get", "__getitem__", "__setitem__", "__contains__"]:
        setattr(cls, name, get_method(name))
    return cls


# Inherits from unicode in Python 2 and str in Python 3.
@istr_methods
class IStr(ustr):
    """Bases: `str` (or `unicode` in Python 2)

    A case-insensitive string class based on `IRC case rules`_. (``{}|^`` are
    lowercase equivalents of ``[]\~``.)

    Equality comparisons are case-insensitive, but the original string is
    preserved. `str` (or `unicode`) can be used to obtain a case-sensitive
    version of the string. For example::

        >>> IStr("STRing^") == "string^"
        True
        >>> IStr("STRing^") == "STRING~"
        True
        >>> str(IStr("STRing^")) == "STRING~"
        False

    Throughout pyrcb, all parameters and attributes that represent nicknames or
    channels are of type `IStr`, so they can be tested for equality without
    worrying about case-sensitivity.

    Arguments are passed to and handled by `str`. This class behaves just like
    `str` (or `unicode`), except for equality comparisons and methods which
    rely on equality comparisons, such as :meth:`str.index`.

    When used as keys in dictionaries, IStr objects will act like the lowercase
    version of the string they represent. If you want a case-insensitive
    dictionary, use `IDefaultDict`.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """

    def __init__(self, *args, **kwargs):
        string = ustr(self)
        self._lower = IStr.make_lower(string)
        self._upper = IStr.make_upper(string)

    def __hash__(self):
        return hash(self._lower)

    def __repr__(self):
        return "IStr({0})".format(super(IStr, self).__repr__())

    def lower(self):
        return self._lower

    def upper(self):
        return self._upper

    # Returns a lowercase version of a string, according to IRC case rules.
    @staticmethod
    def make_lower(string):
        lower = string.lower()
        for char, replacement in zip(r"[]\~", r"{}|^"):
            lower = lower.replace(char, replacement)
        return lower

    # Returns an uppercase version of a string, according to IRC case rules.
    @staticmethod
    def make_upper(string):
        upper = string.upper()
        for char, replacement in zip(r"{}|^", r"[]\~"):
            upper = upper.replace(char, replacement)
        return upper


@idefaultdict_methods
class IDefaultDict(OrderedDict):
    """A case-insensitive `~collections.defaultdict` class based on `IRC case
    rules`_.

    Key equality is case-insensitive. Keys are converted to `IStr` upon
    assignment and retrieval. Keys should be only of type `str` or `IStr`.

    This class is actually a subclass of `~collections.OrderedDict`, so keys
    are kept in the order they were added in, but the functionality of
    `~collections.defaultdict` is still available, and the constructor matches
    that of `~collections.defaultdict` as well.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """
    def __init__(self, default_factory=None, *args, **kwargs):
        super(IDefaultDict, self).__init__(*args, **kwargs)
        self.default_factory = default_factory

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = self.default_factory()
        return self[key]


class Nickname(IStr):
    """A subclass of `IStr` that represents a nickname and also stores the
    associated user's username and hostname.

    In `IRCBot` events, nicknames are sometimes of this type (when the command
    originated from the associated user). See individual methods' descriptions
    more information.

    It shouldn't be necessary to create objects of this type.
    """
    def __new__(cls, *args, **kwargs):
        kwargs.pop("username", None)
        kwargs.pop("hostname", None)
        return super(Nickname, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        try:
            self.username = kwargs.pop("username")
            self.hostname = kwargs.pop("hostname")
        except KeyError:
            raise TypeError(
                "Keyword-only arguments 'username' "
                "and 'hostname' are required.")
        super(Nickname, self).__init__(*args, **kwargs)
