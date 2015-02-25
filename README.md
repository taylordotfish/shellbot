# shellbot
`shellbot` is an IRC bot (using [pyrcb](https://github.com/nickolas360/pyrcb)) that runs shell commands. For example,
```
irc_user: !$ cowsay moo
shellbot:  _____
shellbot: < moo >
shellbot:  -----
shellbot:         \   ^__^
shellbot:          \  (oo)\_______
shellbot:             (__)\       )\/\
shellbot:                 ||----w |
shellbot:                 ||     ||
```

To run a command with `shellbot`, prefix your command with `!$` (and a space).  
Run `shellbot --help` for information on how to run `shellbot`.

`shellbot` has been tested with Python 3 and Debian GNU/Linux, though it should work with most Unix-like operating systems.

Because `shellbot` runs any command it receives, it has the potential to cause serious damage. It is highly recommended that you create a new user with limited permissions and run `shellbot` as that user. Anything that user can run, `shellbot` can run as well.

To prevent users from killing `shellbot`, start it with `sudo -Hiu [user_with_limited_permissions] /path/to/shellbot [options]`. This will run `shellbot` with limited permissions, preventing serious damage, but the process will be owned by `root`.
