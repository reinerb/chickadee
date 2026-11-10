import json
from types import SimpleNamespace
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import Message, TextBlock, Usage
from anthropic.types.messages import (
    MessageBatchExpiredResult,
    MessageBatchIndividualResponse,
    MessageBatchSucceededResult,
)

from chickadee.claude import ClaudeBatches

REVIEW = {
    "content_summary": "A summary.",
    "key_point": "The main finding.",
    "key_point_up_front": True,
    "topics": ["Fish"],
    "score": 7,
    "summary": "Solid basics.",
    "suggested_title": "Title",
    "suggested_description": "Description",
    "issues": [],
}


def message(text: str, stop_reason: Any = "end_turn") -> Message:
    return Message(
        id="msg_1",
        content=[TextBlock(type="text", text=text)],
        model="claude-sonnet-5-5",
        role="assistant",
        stop_reason=stop_reason,
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=1, output_tokens=1),
    )


def succeeded(custom_id: str, msg: Message) -> MessageBatchIndividualResponse:
    return MessageBatchIndividualResponse(
        custom_id=custom_id,
        result=MessageBatchSucceededResult(type="succeeded", message=msg),
    )


def batches_returning(*results: MessageBatchIndividualResponse) -> ClaudeBatches:
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            batches=SimpleNamespace(results=lambda batch_id: iter(results))
        )
    )
    return ClaudeBatches(cast(Anthropic, fake))


def test_results_become_reviews_or_say_why_not():
    batches = batches_returning(
        succeeded("recA-h-v", message(json.dumps(REVIEW))),
        succeeded("recB-h-v", message("not json")),
        succeeded("recC-h-v", message(json.dumps(REVIEW), stop_reason="max_tokens")),
        MessageBatchIndividualResponse(
            custom_id="recD-h-v", result=MessageBatchExpiredResult(type="expired")
        ),
    )

    results = list(batches.results("msgbatch_1"))

    assert results[0].review is not None
    assert results[0].review.score == 7
    assert [(r.custom_id, r.problem) for r in results[1:]] == [
        ("recB-h-v", "no usable review"),
        ("recC-h-v", "no usable review"),
        ("recD-h-v", "expired"),
    ]
