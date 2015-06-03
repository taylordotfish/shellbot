# shellbot
`shellbot` is an IRC bot (using [pyrcb](https://github.com/nickolas360/pyrcb))
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
To prevent this, create a second user with limited permissions, and when
running `shellbot` as the first user with limited permissions, add the option
`-u <second_limited_user>`.

Make sure the first user with limited permissions is able to execute commands
as the second user with `sudo -u` without a password. This can be done by
adding `<first_user> ALL=<second_user> NOPASSWD:ALL` to your `sudoers` file.

*Disclaimer: If not done right, this is potentially very dangerous.*
