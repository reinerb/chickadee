import argparse
from typing import Protocol

from chickadee import (
    alerts,
    audit,
    collect,
    digest,
    flags,
    importer,
    links,
    prune,
    uptime,
)


class Command(Protocol):
    @property
    def HELP(self) -> str: ...

    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    def run(self, args: argparse.Namespace) -> None: ...


COMMANDS: dict[str, Command] = {
    "import": importer,
    "uptime": uptime,
    "audit": audit,
    "collect": collect,
    "links": links,
    "flags": flags,
    "digest": digest,
    "prune": prune,
    "test-alert": alerts,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-monitor",
        description="Keep track of what's on a website, what changed, and what needs attention.",
    )
    subparsers = parser.add_subparsers(
        title="commands", metavar="COMMAND", required=True
    )
    for name, command in COMMANDS.items():
        subparser = subparsers.add_parser(
            name, help=command.HELP, description=command.HELP
        )
        command.add_arguments(subparser)
        subparser.set_defaults(run=command.run)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.run(args)
