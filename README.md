shellbot
========

Version 0.2.0

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

To run a command with shellbot, prefix your command with `!$` (and a space).
`/msg shellbot help` for more information.

See `shellbot --help` for information on how to run it.

Because shellbot runs any command it receives, it has the potential to cause
serious damage. It is *highly recommended* that you create a new user with
limited permissions and run shellbot as that user. Anything that user can run,
shellbot can run as well.

By default, IRC users can kill shellbot by running `!$ kill <shellbot-proc>`.
To prevent this, start shellbot as root and add the option `-u
<shellbot-user>`.

*Disclaimer: If not done properly, running shellbot can be dangerous! You
should set (among other precautions) process limits to avoid fork bombs. Be
aware that users can start long-running processes with calls to setsid() or
setpgrp().*

What's new
----------

Version 0.2.0:

* Freezes/crashes no longer occur when running commands with largs amounts of
  output (such as ``yes``).
* Long lines are now split into multiple IRC messages to avoid truncation.
* Times are now shown next to all logged events.

Dependencies
------------

* Python 3.4 or higher
* [docopt 0.6.6 or higher](https://pypi.python.org/pypi/docopt)
