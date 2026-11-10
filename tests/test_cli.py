import argparse

import pytest

from chickadee.cli import COMMANDS, build_parser
from chickadee.commands import prune
from chickadee.commands._args import positive_int


def test_arguments_reach_the_right_command():
    args = build_parser().parse_args(["prune", "--days", "30", "--dry-run"])

    assert args.run is prune.run
    assert args.days == 30
    assert args.dry_run is True


def test_zero_days_is_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


@pytest.mark.parametrize("name", list(COMMANDS))
def test_every_command_has_working_help(name, capsys):
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args([name, "--help"])

    assert exit_info.value.code == 0
    assert COMMANDS[name].HELP in capsys.readouterr().out
