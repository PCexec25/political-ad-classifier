"""Keyword-rule baseline: the codebook's tie-break rules written as regexes.

Two jobs:
1. Pre-labeling. It suggests labels for a human to check, cutting labeling
   time. It is deliberately NOT an LLM: pre-labeling the gold set with the
   same kind of model being evaluated would make the evaluation circular.
2. Baseline. Any LLM result is only interesting relative to a cheap,
   transparent alternative. `adclass baseline` scores it like any model.

Every prediction carries the keywords that fired, so a reviewer can see
why it chose what it chose and disagree quickly.

Caveat for reporting: the word lists were written with sight of the gold
ads (it's the only data there is), so this baseline's score on that set
is optimistic. Report it on the blind holdout and say so.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import Prediction


def _rx(*patterns: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)


# ---- Goal --------------------------------------------------------------

# Rule 1: an explicit request for money.
MONEY_ASK = _rx(
    r"chip(?:ping)? in", r"pitch in", r"donat(?:e|es|ed|ing|ion|ions)", r"contribut(?:e|ion|ions)",
    r"give (?:now|today|\$\d|anything|whatever|what you can|\d)", r"rush (?:a |\$|over a )?(?:donation|\d)",
    r"(?:make|send) (?:a |your )?(?:gift|donation|contribution)", r"gift of", r"founding donor",
    r"monthly (?:gift|donor|donation)", r"every dollar", r"fund(?:raising)? (?:goal|deadline)",
    r"matched", r"your gift",
)

# Rule 2: practical voting information, or a petition / pledge / volunteer ask.
VOTING_INFO = _rx(
    r"register(?:ed)? to vote", r"voter registration", r"registration (?:is|deadline)", r"your registration",
    r"polling place", r"where to vote", r"early voting", r"absentee", r"mail ballot", r"request (?:a |your )?ballot",
    r"make a plan to vote", r"plan to vote", r"voting information", r"election day is",
)
CIVIC_ACTION = _rx(
    r"sign (?:the |our |this )?petition", r"sign here", r"sign now", r"sign your name", r"add your name",
    r"pledge", r"volunteer", r"rsvp", r"join (?:us|our) (?:at|on)",
)

# Rule 3: a named-candidate vote ask stays persuasion; we only need to know
# the ad is political at all, versus a product, service, or lead-gen ad.
POLITICAL = _rx(
    r"vote", r"voters?", r"elect(?:ed|ion)?", r"re-?elect", r"governor", r"congress(?:man|woman)?", r"senat(?:e|or)",
    r"assembly", r"state (?:house|rep\w*)", r"legislat\w+", r"mayor", r"judge", r"attorney general", r"district attorney",
    r"trump", r"democrat\w*", r"republican\w*", r"gop", r"maga", r"campaign", r"candidate", r"vetoe?d?s?",
    r"washington", r"politicians?", r"too extreme", r"radical\w*",
)
NON_POLITICAL_OFFER = _rx(
    r"free (?:e-?book|pdf|review|quiz)", r"take the quiz", r"stream (?:it|now)", r"subscription", r"shop now",
    r"call us", r"book your appointment", r"schedule a\w*", r"click follow", r"sign up free", r"use code",
)

# ---- Issue -------------------------------------------------------------

ISSUE_LEXICON: dict[str, re.Pattern[str]] = {
    "economy": _rx(
        r"inflation", r"prices?", r"costs?", r"cost of living", r"afford\w*", r"tax(?:es)?", r"wages?", r"jobs",
        r"grocer\w*", r"gas", r"rent", r"utilit(?:y|ies)", r"electric\w*", r"bills", r"tariffs?", r"econom\w+",
        r"budget", r"small business\w*", r"paychecks?", r"housing", r"rate hikes?",
    ),
    "healthcare": _rx(
        r"health ?care", r"health insurance", r"insurance", r"medicare", r"medicaid", r"premiums",
        r"drug (?:companies|prices)", r"prescriptions?", r"coverage", r"hospitals?", r"aca", r"obamacare",
        r"social security",
    ),
    "abortion": _rx(
        r"abortions?", r"roe", r"reproductive", r"pro-?life", r"pro-?choice", r"preborn", r"unborn",
        r"birth control", r"contracepti\w+", r"mifepristone", r"ivf", r"planned parenthood", r"save babies",
        r"life defender", r"women'?s (?:health|bodies|rights)", r"their bodies",
    ),
    "immigration": _rx(
        r"borders?", r"illegal aliens?", r"illegal immigration", r"immigra\w+", r"migrants?", r"asylum",
        r"deport\w*", r"the wall", r"a wall", r"sanctuary", r"border patrol", r"refugees?",
    ),
    "democracy_voting": _rx(
        r"democracy", r"voting rights", r"election (?:integrity|rigging)", r"rigging", r"supreme court",
        r"constitution\w*", r"ballot access", r"project 2025", r"power grab", r"first amendment",
        r"free speech", r"censorship", r"the courts?", r"justices?",
    ),
    "public_safety": _rx(
        r"crime", r"criminals?", r"police", r"law enforcement", r"sheriff", r"prosecut\w+", r"violent",
        r"public safety", r"safer", r"keep \w+ (?:families |communities )?safe", r"guns?", r"fentanyl", r"cartels?",
        r"traffick\w+", r"murder", r"victims", r"back(?:ing)? the blue", r"exploitation", r"predators?",
    ),
    "candidate_character": _rx(
        r"corrupt\w*", r"scandal", r"lies", r"liar", r"can'?t trust", r"cannot trust", r"too extreme",
        r"veteran", r"navy seal", r"outsider", r"grew up", r"generation", r"father of", r"mother of",
        r"his record", r"her record", r"honest\w*",
    ),
}
# When counts tie, prefer the more specific topic.
ISSUE_PRIORITY = ("abortion", "immigration", "public_safety", "healthcare", "democracy_voting", "economy", "candidate_character")


@dataclass(frozen=True)
class RuleResult:
    goal: str
    issue: str
    confidence: str
    reason: str


def _hits(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.group(0).lower() for m in pattern.finditer(text)]


def _short(words: list[str], n: int = 3) -> str:
    seen: list[str] = []
    for w in words:
        if w not in seen:
            seen.append(w)
    return ", ".join(f'"{w}"' for w in seen[:n])


def classify_text(text: str) -> RuleResult:
    money = _hits(MONEY_ASK, text)
    info = _hits(VOTING_INFO, text) + _hits(CIVIC_ACTION, text)
    political = _hits(POLITICAL, text)
    offer = _hits(NON_POLITICAL_OFFER, text)

    if money:
        goal, goal_why, goal_conf = "fundraising", f"money ask {_short(money)} (rule 1)", "high"
    elif info:
        goal, goal_why, goal_conf = "mobilization", f"civic action {_short(info)} (rule 2)", "high"
    elif offer:
        goal, goal_why, goal_conf = "other", f"product/lead-gen offer {_short(offer)}", "medium"
    elif political:
        goal, goal_why, goal_conf = "persuasion", f"political, no ask {_short(political)}", "medium"
    else:
        # Every ad here came from the political-ad library, so persuasion is the prior.
        goal, goal_why, goal_conf = "persuasion", "no ask found; default for political ads", "low"

    counts = {issue: _hits(rx, text) for issue, rx in ISSUE_LEXICON.items()}
    best = max(counts.values(), key=len)
    if not best:
        issue, issue_why, issue_conf = "other", "no topic keywords", "low"
    else:
        top = max(len(v) for v in counts.values())
        tied = [i for i in ISSUE_PRIORITY if len(counts[i]) == top]
        issue = tied[0]
        issue_why = f"{issue} {_short(counts[issue])}" + (f" (tie with {', '.join(tied[1:])})" if len(tied) > 1 else "")
        issue_conf = "low" if len(tied) > 1 or top == 1 else "medium"

    order = {"low": 0, "medium": 1, "high": 2}
    confidence = min(goal_conf, issue_conf, key=order.__getitem__)
    return RuleResult(goal, issue, confidence, f"goal: {goal_why}; issue: {issue_why}")


def predict(ad_id: str, text: str) -> Prediction:
    r = classify_text(text)
    return Prediction(
        ad_id=ad_id, goal=r.goal, issue=r.issue, confidence=r.confidence, rationale=r.reason,
        prompt_version="rules-v1", model="keyword-baseline",
    )
