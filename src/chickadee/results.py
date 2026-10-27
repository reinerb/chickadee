from dataclasses import dataclass
from typing import Literal

LinkStatus = Literal["ok", "broken", "unverified"]


@dataclass(frozen=True)
class LinkResult:
    url: str
    status: LinkStatus
    detail: str
