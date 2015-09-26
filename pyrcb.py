# Copyright (C) 2015 taylor.fish (https://github.com/taylordotfish)
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
from collections import defaultdict
import errno
import re
import socket
import ssl
import threading
import time

__version__ = "1.7.1"


class IRCBot(object):
    """The base class for IRC bots.

    IRC bots should inherit from this class and override any events they wish
    to handle.

    Instances of this class are reusable.

    :param bool debug_print: Whether or not communication with the IRC server
      should be printed.
    :param callable print_function: The print function to be used if
      ``debug_print`` is true. Should accept a single string argument.
    :param bool delay: Whether or not sent messages should be delayed to avoid
      server throttling or spam prevention.
    """
    def __init__(self, debug_print=False, print_function=print, delay=True):
        self.debug_print = debug_print
        self.print_function = print_function
        self.delay = delay

    # Initializes attributes.
    def _init_attr(self):
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

        # Buffer of delayed messages. Stores tuples of
        # the time to be sent and the message text.
        self._delay_buffer = []
        # Maps a channel/nickname to the time of the most recent message
        # sent and how many messages without a break have been sent.
        self.last_sent = IDefaultDict(lambda: (0, 0))
        self.delay_event = threading.Event()
        self.listen_event = threading.Event()

    # ==================
    # Public IRC methods
    # ==================

    def connect(self, hostname, port, use_ssl=False, ca_certs=None):
        """Connects to an IRC server.

        :param str hostname: The hostname of the IRC server.
        :param int port: The port of the IRC server.
        :param bool use_ssl: Whether or not to use SSL/TLS.
        :param str ca_certs: The path to a list of trusted CA certificates (to
          be passed to :func:`ssl.wrap_socket`). If provided, the certificate
          received from the IRC server and the server's hostname will be
          verified.
        """
        self._init_attr()
        self.hostname = hostname
        self.port = port
        self.socket.connect((hostname, port))
        if use_ssl:
            reqs = ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE
            self.socket = ssl.wrap_socket(
                self.socket, cert_reqs=reqs, ca_certs=ca_certs)
            if ca_certs:
                ssl.match_hostname(self.socket.getpeercert(), hostname)

        self.alive = True
        if self.delay:
            t = threading.Thread(target=self.delay_loop)
            t.daemon = True
            t.start()

    def password(self, password):
        """Sets a connection password. (``PASS`` command.)

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
                return
            self._handle(line)

    def join(self, channel):
        """Joins a channel. (``JOIN`` command.)

        :param str channel: The channel to join. Must start with the channel
          prefix.
        """
        self.send_raw("JOIN", [channel])

    def part(self, channel, message=None):
        """Leaves a channel. (``PART`` command.)

        :param str channel: The channel to leave. Must start with the channel
          prefix.
        :param str message: An optional part message.
        """
        self.send_raw("PART", filter(None, [channel, message]))

    def quit(self, message=None):
        """Disconnects from the server. (``QUIT`` command.)

        :param str message: An optional quit message.
        """
        try:
            self.send_raw("QUIT", filter(None, [message]))
        finally:
            self.close_socket()

    def send(self, target, message):
        """Sends a message to a channel or user. (``PRIVMSG`` command.)

        :param str target: The recipient of the message: either a channel or
          the nickname of a user.
        :param str message: The message to send.
        """
        self.add_delayed(target, "PRIVMSG", [target, message])

    def send_notice(self, target, message):
        """Sends a notice to a channel or user. (``NOTICE`` command.)

        :param str target: The recipient of the notice: either a channel or the
          nickname or a user.
        :param str notice: The notice to send.
        """
        self.add_delayed(target, "NOTICE", [target, message])

    def nick(self, new_nickname):
        """Changes the bot's nickname. (``NICK`` command.)

        :param str new_nickname: The bot's new nickname.
        """
        self.send_raw("NICK", [new_nickname])

    def names(self, channel):
        """Requests a list of users in a channel. (``NAMES`` command.)

        Calling this method is usually unnecessary because bots automatically
        keep track of users in joined channels. See `IRCBot.nicklist`.

        :param str channel: The channel to request a list of users from.
        """
        if not channel.isspace():
            self.send_raw("NAMES", [channel])

    def send_raw(self, command, args=[]):
        """Sends a raw IRC message.

        :param str command: The command to send.
        :param list args: A list of arguments to the command.
        """
        self.writeline(IRCBot.format(command, args))

    # =================
    # Public IRC events
    # =================

    def on_join(self, nickname, channel):
        """Called when a user joins a channel. (``JOIN`` command.)

        :param IStr nickname: The nickname of the user.
        :param IStr channel: The channel being joined.
        """

    def on_part(self, nickname, channel, message):
        """Called when a user leaves a channel. (``PART`` command.)

        :param IStr nickname: The nickname of the user.
        :param IStr channel: The channel being left.
        :param str message: The part message.
        """

    def on_quit(self, nickname, message, channels):
        """Called when a user disconnects from the server. (``QUIT`` command.)

        :param IStr nickname: The nickname of the user.
        :param str message: The quit message.
        :param list channels: A list of channels the user was in.
        """

    def on_kick(self, nickname, channel, target, message):
        """Called when a user is kicked from a channel. (``KICK`` command.)

        :param IStr nickname: The nickname of the user who is kicking someone.
        :param IStr channel: The channel someone is being kicked from.
        :param IStr target: The nickname of the user being kicked. Check if
          this is equal to ``self.nickname`` to check if this bot was kicked.
        :param str message: The kick message.
        """

    def on_message(self, message, nickname, channel, is_query):
        """Called when a message is received. (``PRIVMSG`` command.)

        :param str message: The text of the message.
        :param IStr nickname: The nickname of the user who sent the message.
        :param IStr channel: The channel the message is in. If sent in a
          private query, this is `None`.
        :param bool is_query: Whether or not the message was sent to this bot
          in a private query.
        """

    def on_notice(self, message, nickname, channel, is_query):
        """Called when a notice is received. (``NOTICE`` command.)

        :param str message: The text of the notice.
        :param IStr nickname: The nickname of the user who sent the notice.
        :param IStr channel: The channel the notice is in. If sent in a private
          query, this is `None`.
        :param bool is_query: Whether or not the notice was sent to this bot in
          a private query.
        """

    def on_nick(self, nickname, new_nickname):
        """Called when a user changes nicknames. (``NICK`` command.)

        :param IStr nickname: The user's old nickname.
        :param IStr new_nickname: The user's new nickname.
        """

    def on_names(self, channel, names):
        """Called when a list of users in a channel is received.

        :param IStr channel: The channel that the list of users describes.
        :param list names: A list of nicknames of users in the channel.
          Nicknames are of type `IStr`.
        """

    def on_raw(self, nickname, command, args):
        """Called when any IRC message is received.

        :param IStr nickname: The nickname of the user who sent the message.
        :param IStr command: The command (or numeric reply) received.
        :param list args: A list of arguments to the command. Arguments are of
          type `str`.
        """

    # ====================
    # Other public methods
    # ====================

    def listen(self):
        """Listens for incoming messages and calls the appropriate events.

        This method is blocking. Either this method or :meth:`listen_async`
        should be called after registering and joining channels.
        """
        try:
            self._listen()
        finally:
            self.listen_event.set()
            self.close_socket()

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
                self.listen()
            finally:
                if callback:
                    callback()
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
        :returns: `True` if the method returned because the bot lost
          connection or `False` if the operation timed out.
        """
        return self.listen_event.wait(timeout)

    # ===============
    # Private methods
    # ===============

    # Method which actually listens for incoming messages.
    # Wrapped in try-finally clause in the public method listen().
    def _listen(self):
        while True:
            try:
                line = self.readline()
            except socket.error as e:
                if e.errno not in [errno.EPIPE, errno.ENOTCONN]:
                    raise
                return
            if line is None:
                return
            self._handle(line)

    # Parses an IRC message and calls the appropriate event.
    def _handle(self, message, async_events=False):
        nick, cmd, args = IRCBot.parse(message)
        if cmd in ["JOIN", "PART", "KICK"]:
            channel = IStr(args[0])

        if cmd == "001":  # RPL_WELCOME
            self.is_registered = True
        elif cmd == "PING":
            self.send_raw("PONG", args)
        elif cmd == "JOIN":
            self.add_nickname(nick, [channel])
            self.on_join(nick, channel)
        elif cmd == "PART":
            self.remove_nickname(nick, [channel])
            part_msg = (args + [None])[1]
            self.on_part(nick, channel, part_msg)
        elif cmd == "QUIT":
            channels = self.remove_nickname(nick, self.channels)
            self.on_quit(nick, args[-1], channels)
        elif cmd == "KICK":
            self.remove_nickname(args[1], [channel])
            self.on_kick(nick, channel, IStr(args[1]), args[-1])
        elif cmd == "NICK":
            self.replace_nickname(nick, args[0])
            self.on_nick(nick, IStr(args[0]))
        elif cmd in ["PRIVMSG", "NOTICE"]:
            is_query = args[0] == self.nickname
            channel = (IStr(args[0]), None)[is_query]
            [self.on_message, self.on_notice][cmd == "NOTICE"](
                args[-1], nick, channel, is_query)
        elif cmd == "353":  # RPL_NAMREPLY
            channel = IStr(args[2])
            names = [IStr(n.lstrip("@+")) for n in args[-1].split()]
            self._names_buffer[channel] += names
        elif cmd == "366":  # RPL_ENDOFNAMES
            self.nicklist.update(self._names_buffer)
            for channel, names in self._names_buffer.items():
                self.on_names(channel, names)
            if args[1] not in self._names_buffer:
                self.on_names(IStr(args[1]), [])
            self._names_buffer.clear()
        elif cmd == "433":  # ERR_NICKNAMEINUSE
            if not self.is_registered:
                raise ValueError("Nickname is already in use.")
        self.on_raw(nick, cmd, args)

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
        for channel in channels:
            nicklist = self.nicklist[channel]
            if nickname in nicklist:
                if nickname == self.nickname:
                    if channel in self.channels:
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

    # Parses an IRC message.
    @staticmethod
    def parse(message):
        # Regex to parse IRC messages
        match = re.match(r"(?::([^!@ ]+)[^ ]* )?([^ ]+)"
                         r"((?: [^: ][^ ]*){0,14})(?: :?(.+))?",
                         message)

        nick, cmd, args, trailing = match.groups("")
        args = args.split()
        if trailing:
            args.append(trailing)
        return (IStr(nick), IStr(cmd), args)

    # Formats an IRC message.
    @staticmethod
    def format(command, args=[]):
        str_args = list(map(str, args))
        if any(arg is None for arg in args):
            raise ValueError("Arguments cannot be None.")
        if not all(str_args):
            raise ValueError("Arguments cannot be empty strings.")
        if any(any(c in arg for c in "\0\r\n") for arg in str_args):
            raise ValueError(r"Arguments cannot contain '\0', '\r', or '\n'.")
        if any(any(c in arg for c in " :") for arg in str_args[:-1]):
            raise ValueError("Only the last argument can contain ' ' or ':'.")
        if str_args:
            str_args[-1] = ":" + str_args[-1]
            return command + " " + " ".join(str_args)
        return command

    # Adds a delayed message, or sends the message if delays are off.
    def add_delayed(self, target, command, args):
        if not self.delay:
            self.send_raw(command, args)
            return

        last_time, consecutive = self.last_sent[target]
        last_delta = time.time() - last_time
        if last_delta >= 5:
            consecutive = 0

        delay = min(consecutive / 10, 1.5)
        message_time = max(last_time, time.time()) + delay
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
                delay = message_time - time.time()

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
            if e.errno not in [errno.EPIPE, errno.ENOTCONN]:
                raise
        finally:
            self.alive = False
            self.delay_event.set()


# Returns a lowercase version of a string, according to IRC case rules.
def irc_lower(string):
    lower = string.lower()
    for c, r in zip(r"[]\~", r"{}|^"):
        lower = lower.replace(c, r)
    return lower


# Returns an uppercase version of a string, according to IRC case rules.
def irc_upper(string):
    upper = string.upper()
    for c, r in zip(r"{}|^", r"[]\~"):
        upper = upper.replace(c, r)
    return upper


# Decorator to implement case-insensitive operators for IStr.
def istr_operators(cls):
    def get_method(name):
        def method(self, other):
            if isinstance(other, str):
                other = irc_lower(other)
            return getattr(self._lower, name)(other)
        return method
    for name in ("lt", "le", "ne", "eq", "gt", "ge", "contains"):
        name = "__{0}__".format(name)
        setattr(cls, name, get_method(name))
    return cls


# Decorator to implement case-insensitive methods for IStr.
def istr_methods(cls):
    def get_method(name):
        def method(self, string, start=None, end=None):
            return getattr(self._lower, name)(irc_lower(string), start, end)
        return method
    for name in ("index", "find", "count", "startswith", "endswith"):
        setattr(cls, name, get_method(name))
    return cls


@istr_operators
@istr_methods
# Inherit from unicode() in Python 2 and str() in Python 3.
class IStr(type("")):
    """Bases: `str` (`unicode` in Python 2)

    A case-insensitive string class based on `IRC case rules`_.

    Equality comparisons are case-insensitive, but the original string is
    preserved. `str` (or `unicode`) can be used to obtain a case-sensitive
    version of the string. For example::

        >>> IStr("string") == "string"
        True
        >>> IStr("string") == "STRING"
        True
        >>> str(IStr("string")) == "STRING"
        False

    All ``nickname``, ``channel``, and ``target`` parameters in IRCBot events
    are of type `IStr`, so they can be tested for equality without worrying
    about case-sensitivity.

    Arguments are passed to and handled by `str`. This class behaves just like
    `str` (or `unicode`), except for equality comparisons and methods which
    rely on equality comparisons, such as :meth:`str.index`.

    IRC case rules state that ``{}|^`` are lowercase equivalents of ``[]\~``.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """

    def __init__(self, *args, **kwargs):
        string = type("")(self)
        self._lower = irc_lower(string)
        self._upper = irc_upper(string)

    def __hash__(self):
        return hash(self._lower)

    def lower(self):
        return self._lower

    def upper(self):
        return self._upper


class IDefaultDict(defaultdict):
    """A case-insensitive `~collections.defaultdict` class based on `IRC case
    rules`_.

    Key equality is case-insensitive. Keys are converted to `IStr` upon
    assignment and retrieval. Keys should be only of type `str` or `IStr`.

    .. _IRC case rules: https://tools.ietf.org/html/rfc2812#section-2.2
    """

    def __getitem__(self, key):
        return super(IDefaultDict, self).__getitem__(IStr(key))

    def __setitem__(self, key, value):
        super(IDefaultDict, self).__setitem__(IStr(key), value)
