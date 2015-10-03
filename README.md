shellbot
========

Version 0.1.6

**shellbot** is an IRC bot (using [pyrcb]) that runs shell commands.
For example,

[pyrcb]: https://github.com/taylordotfish/pyrcb

```
<irc_user> !$ cowsay moo
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
serious damage. It is highly recommended that you create a new user with
limited permissions and run shellbot as that user. Anything that user can run,
shellbot can run as well.

By default, IRC users can kill shellbot by running `!$ kill <shellbot-proc>`.
To prevent this, start shellbot as root and add the option `-u <limited-user>`.

*Disclaimer: If not done properly, running shellbot can be very dangerous! In
addition to the steps above, you should set (among other precautions) process
limits to avoid fork bombs.*

Dependencies
------------

* Python 3.3 or higher
* [docopt 0.6.6 or higher](https://pypi.python.org/pypi/docopt)
