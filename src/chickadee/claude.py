"""Claude's Message Batches API, spoken to in Chickadee's own types."""

from collections.abc import Iterator, Sequence

from anthropic import Anthropic
from anthropic.types.messages.batch_create_params import Request

from chickadee.collect import ReviewResult
from chickadee.reviewer import parse_review


class ClaudeBatches:
    def __init__(self, client: Anthropic) -> None:
        self._client = client

    def submit(self, requests: Sequence[Request]) -> str:
        return self._client.messages.batches.create(requests=list(requests)).id

    def status(self, batch_id: str) -> str:
        return self._client.messages.batches.retrieve(batch_id).processing_status

    def results(self, batch_id: str) -> Iterator[ReviewResult]:
        for result in self._client.messages.batches.results(batch_id):
            outcome = result.result
            if outcome.type != "succeeded":
                yield ReviewResult(result.custom_id, None, outcome.type)
                continue

            review = parse_review(outcome.message)
            problem = None if review else "no usable review"
            yield ReviewResult(result.custom_id, review, problem)
