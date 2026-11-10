from contextlib import ExitStack
from functools import cached_property
from types import TracebackType
from typing import Self

import httpx
from pyairtable import Api

from chickadee.airtable import AirtablePages
from chickadee.checker import make_client
from chickadee.config import Options, Settings, load_options, load_settings


class App:
    """Builds what commands need, the first time they ask for it.

    Nothing is read or opened up front, so a command only needs the
    configuration it actually uses. Anything opened here is closed
    when the `with` block ends, even if the command fails.
    """

    def __init__(self) -> None:
        self._stack = ExitStack()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType,
    ):
        self._stack.close()

    @cached_property
    def settings(self) -> Settings:
        return load_settings()

    @cached_property
    def options(self) -> Options:
        return load_options()

    @cached_property
    def http(self) -> httpx.Client:
        return self._stack.enter_context(make_client())

    @cached_property
    def airtable(self) -> Api:
        return Api(self.settings.airtable_token)

    @cached_property
    def pages(self) -> AirtablePages:
        table = self.airtable.table(self.settings.airtable_base_id, "Pages")
        return AirtablePages(table)
