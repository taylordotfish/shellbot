shellbot
========

Version 0.2.15

**shellbot** is an [IRC bot] that runs shell commands.
For example,

[IRC bot]: https://github.com/taylordotfish/pyrcb

```
<irc-user> !$ cowsay moo
<shellbot>  _____
<shellbot> < moo >
<shellbot>  -----
<shellbot>         \   ^__^
<shellbot>          \  (oo)\_______
<shellbot>             (__)\       )\/\
<shellbot>                 ||----w |
<shellbot>                 ||     ||
```

To run a command with shellbot, prefix your command with ``!$`` (and a space).
``/msg shellbot help`` for more information.

shellbot should work on any Unix-like operating system. See ``shellbot --help``
for information on how to run it.

Because shellbot runs any command it receives, it has the potential to cause
serious damage. It is *highly recommended* that you create a new user with
limited permissions and run shellbot as that user. Anything that user can run,
shellbot can run as well.

By default, IRC users can kill shellbot by running ``!$ kill <shellbot-proc>``.
To prevent this, start shellbot as root and add the option ``-u
<shellbot-user>``.

*Warning: If not done properly, running shellbot can be dangerous! You
should set (among other precautions) process limits to avoid fork bombs. Be
aware that users can start long-running processes with calls to setsid() or
setpgrp().*

What's new
----------

Version 0.2.15:

* Updated pyrcb.

Version 0.2.14:

* Fixed syntax error with older versions of Python.

Version 0.2.11-0.2.13:

* Updated pyrcb.

Version 0.2.x:

* Fixed an issue with the ``--path`` option.
* Fixed a bug where invalid characters in command output could crash shelldon.
* Fixed an issue with command timeouts that allowed processes to take up too
  much time.
* Freezes/crashes no longer occur when running commands with largs amounts of
  output (such as ``yes``).
* Long lines are now split into multiple IRC messages to avoid truncation.
* Times are now shown next to all logged events.

Dependencies
------------

* Python 3.4 or higher
* [docopt 0.6.6 or higher](https://pypi.python.org/pypi/docopt)
* [Bash](https://www.gnu.org/software/bash/)
