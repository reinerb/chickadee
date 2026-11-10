class ChickadeeError(Exception):
    """An error we expect, with a message meant for the user.
    Raise it anywhere. Only `cli.main` turns it into an exit code.
    """


class ConfigError(ChickadeeError):
    pass
