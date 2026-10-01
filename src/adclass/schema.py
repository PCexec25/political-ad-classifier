"""Label taxonomy and record types.

The label sets here are the single source of truth: the prompt, the
tool schema sent to the model, the gold-set validator, and the metrics
all read from these tuples. Change a label here and everything follows.
See CODEBOOK.md for the human-readable definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

GOALS: tuple[str, ...] = (
    "persuasion",
    "mobilization",
    "fundraising",
    "other",
)

ISSUES: tuple[str, ...] = (
    "economy",
    "healthcare",
    "abortion",
    "immigration",
    "democracy_voting",
    "candidate_character",
    "public_safety",
    "other",
)

CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")


@dataclass(frozen=True)
class Ad:
    """One ad to classify. Only `ad_id` and `text` are required."""

    ad_id: str
    text: str
    page_name: str = ""
    source_url: str = ""


@dataclass(frozen=True)
class GoldLabel:
    """A human-assigned label for one ad."""

    ad_id: str
    goal: str
    issue: str

    def __post_init__(self) -> None:
        if self.goal not in GOALS:
            raise ValueError(f"{self.ad_id}: unknown goal {self.goal!r}; expected one of {GOALS}")
        if self.issue not in ISSUES:
            raise ValueError(f"{self.ad_id}: unknown issue {self.issue!r}; expected one of {ISSUES}")


@dataclass
class Prediction:
    """A model-assigned label for one ad, plus provenance for auditing."""

    ad_id: str
    goal: str
    issue: str
    confidence: str
    rationale: str
    prompt_version: str
    model: str
    error: str | None = None
    usage: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None
