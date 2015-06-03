# shellbot
`shellbot` is an IRC bot (using [pyrcb](https://github.com/taylordotfish/pyrcb))
that runs shell commands. For example,
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

To run a command with `shellbot`, prefix your command with `!$` (and a space).
Run `shellbot --help` for information on how to run `shellbot`.

`shellbot` has been tested with Python 3.4 and Debian GNU/Linux, though it
should work with Python 3.3 or higher on most Unix-like operating systems.

Because `shellbot` runs any command it receives, it has the potential to cause
serious damage. It is highly recommended that you create a new user with
limited permissions and run `shellbot` as that user. Anything that user can
run, `shellbot` can run as well.

By default, IRC users can kill `shellbot` by running `!$ kill <shellbot_proc>`.
To prevent this, start `shellbot` as `root` and add the option `-u <limited_user>`.

*Disclaimer: If not done properly, this can be very dangerous! In addition to
the steps above, you should set process limits to avoid fork bombs.*
