from contextlib import ExitStack
from functools import cached_property
from types import TracebackType
from typing import Self

import httpx
from anthropic import Anthropic
from pyairtable import Api, Table

from chickadee.airtable import (
    AirtableBatches,
    AirtableChecks,
    AirtablePages,
    AirtableSite,
    AirtableTopics,
)
from chickadee.checker import make_client
from chickadee.claude import ClaudeBatches
from chickadee.config import (
    Options,
    Settings,
    load_anthropic_key,
    load_options,
    load_settings,
)


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

    def _table(self, name: str) -> Table:
        return self.airtable.table(self.settings.airtable_base_id, name)

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
    def claude(self) -> Anthropic:
        return self._stack.enter_context(Anthropic(api_key=load_anthropic_key()))

    @cached_property
    def pages(self) -> AirtablePages:
        return AirtablePages(self._table("Pages"))

    @cached_property
    def checks(self) -> AirtableChecks:
        return AirtableChecks(self._table("Checks"))

    @cached_property
    def topics(self) -> AirtableTopics:
        return AirtableTopics(self._table("Topics"))

    @cached_property
    def site(self) -> AirtableSite:
        return AirtableSite(self._table("Site"))

    @cached_property
    def audit_batches(self) -> AirtableBatches:
        return AirtableBatches(self._table("Audit batches"))

    @cached_property
    def claude_batches(self) -> ClaudeBatches:
        return ClaudeBatches(self.claude)
