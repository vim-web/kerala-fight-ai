"""Anger arc and fight state management.

Features:
- Pure synchronous step calculations for unit testing.
- Round win detection ("i win", "ഞാൻ ജയിച്ചു", "njan jayichu").
- Fight session state tracking memory notes, round counter, and used insults.
"""

import re
import time
from typing import List, Optional, Set

MIN_ANGER = 0
MAX_ANGER = 10
MAX_STEP_UP = 2  # anger cannot jump more than this in one message
MAX_STEP_DOWN = 3

_SPACE = re.compile(r"\s+")

# Apologising
_APOLOGY = re.compile(
    r"\b(sorry|my bad|my fault|my mistake|i was wrong|i messed up|apologi[sz]e|"
    r"forgive me|kshamikk\w*|pizha\w*|njan thett\w*|thettu patti)\b",
    re.I,
)

# Taking responsibility or naming a concrete next step.
_OWNERSHIP = re.compile(
    r"\b(i should have|i could have|next time|from now on|i will fix|i'll fix|"
    r"my responsibility|i take responsibility|i understand|i hear you|"
    r"you're right|youre right|fair enough|manassilayi|mansilayi|ini njan|"
    r"njan sheriyakkam)\b",
    re.I,
)

# Calm, cooperative language. Two or more markers count.
_CALM = re.compile(
    r"\b(please|let's talk|lets talk|talk about|calm down|shantham|"
    r"listen to you|understand your|appreciate|thank you|thanks|respect|"
    r"sheri|nalla reethi)\b",
    re.I,
)

# Specific detail: a reason, a commitment, or a number/date.
_SPECIFIC = re.compile(
    r"\b(because|when i|next time|i will|i'll|so that|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\d",
    re.I,
)

# Insults aimed at the other person, English and Manglish.
_INSULT = re.compile(
    r"\b(fuck\w*|shit\w*|bastard|asshole|bitch|damn|hell|idiot|stupid|dumb|"
    r"useless|worthless|incompetent|moron|fool|nonsense|myre|patti|thendi|"
    r"pooru|koora|mandan|pulley|pulle)\b",
    re.I,
)

# Win conditions to end the round
_WIN = re.compile(
    r"\b(i win|i won|i have won|ഞാൻ ജയിച്ചു|njan jayichu|njan jeyichu)\b",
    re.I,
)


def normalize(text: str) -> str:
    return _SPACE.sub(" ", (text or "").lower()).strip()


def is_win(text: str) -> bool:
    """Return True if user declared victory in English, Manglish, or Malayalam."""
    body = normalize(text)
    return bool(_WIN.search(body)) or "ഞാൻ ജയിച്ചു" in body


def _is_spam(body: str) -> bool:
    """Keyboard mashing, pure punctuation, or one letter repeated."""
    if len(body) < 2:
        return True
    if any("\u0d00" <= ch <= "\u0d7f" for ch in body):
        return False  # Malayalam script: the ASCII checks below do not apply
    if len(re.sub(r"[^a-z]", "", body)) < 3:
        return True
    if re.fullmatch(r"(.)\1{3,}", body):
        return True
    words = re.findall(r"[a-z]{5,}", body)
    return bool(words) and all(not re.search(r"[aeiouy]", w) for w in words)


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9\u0d00-\u0d7f]+", text.lower()))


def _is_duplicate(body: str, previous: list) -> bool:
    """Near-identical to one of the last few user messages."""
    current = _tokens(body)
    if not current:
        return False
    for older in previous:
        other = _tokens(older)
        if other and len(current & other) / len(current | other) >= 0.85:
            return True
    return False


def step(text: str, previous: Optional[list] = None) -> int:
    """Anger change for one user message. Negative calms, positive angers."""
    previous = previous or []
    body = normalize(text)
    if _is_spam(body) or _is_duplicate(body, previous):
        return 0

    change = 0
    if len(body) >= 40:
        change -= 2  # a real, developed reply
    elif len(body) >= 15:
        change -= 1  # at least a sentence

    if _APOLOGY.search(body):
        change -= 1
    if _OWNERSHIP.search(body) or _SPECIFIC.search(body):
        change -= 1
    if len(_CALM.findall(body)) >= 2:
        change -= 2

    if _INSULT.search(body):
        change = max(1, change + 1)  # insults can raise, never calm

    return max(-MAX_STEP_DOWN, min(MAX_STEP_UP, change))


def apply(current: int, change: int) -> int:
    return max(MIN_ANGER, min(MAX_ANGER, current + change))


def judge_bonus(verdict: Optional[dict]) -> int:
    """One point of extra movement from the optional judge. Never more."""
    if not verdict:
        return 0
    try:
        calm = int(verdict.get("user_calm", 5))
    except (TypeError, ValueError):
        return 0
    if calm >= 8 and verdict.get("addressed_point"):
        return -1
    if calm <= 3:
        return 1
    return 0


def steps_from_history(texts: list) -> list:
    """Deterministic steps over a whole conversation, for stateless scoring."""
    steps, seen = [], []
    for text in texts:
        steps.append(step(text, seen[-3:]))
        seen.append(text)
    return steps


def calm_score(start: int, end: int, steps: list) -> dict:
    """0-100 summary of the session, plus a plain-language label."""
    good = sum(1 for s in steps if s <= -2)
    bad = sum(1 for s in steps if s >= 1)
    behaviour = max(0, min(100, 50 + 12 * good - 15 * bad))

    if start > 0:
        drop = max(0.0, (start - end) / start)
        score = round(60 * drop + 0.4 * behaviour)
    else:
        score = round(behaviour)

    if score >= 80:
        label = "Very calm"
    elif score >= 55:
        label = "Calmer than you started"
    elif score >= 35:
        label = "About the same"
    else:
        label = "Still tense"

    return {
        "score": score,
        "label": label,
        "start": start,
        "end": end,
        "calmer": end < start if start > 0 else None,
    }


class Session:
    """Anger and fight state for one conversation."""

    def __init__(self, start: int):
        self.start = start
        self.anger = start
        self.steps: list = []
        self.turns = 0
        self.round_number = 1
        self.round_over = False
        self.session_notes: List[str] = []
        self.used_insults: List[str] = []  # Last 10 comebacks/insults
        self.touched = time.time()

    def turn(self, change: int) -> int:
        self.steps.append(change)
        self.anger = apply(self.anger, change)
        self.turns += 1
        self.touched = time.time()
        return self.anger

    def add_note(self, note: str) -> None:
        if note and len(note) > 3:
            self.session_notes.append(note[:80])
            if len(self.session_notes) > 10:
                self.session_notes.pop(0)

    def add_used_insult(self, insult: str) -> None:
        if insult:
            clean = insult.strip()
            if clean and clean not in self.used_insults:
                self.used_insults.append(clean)
                if len(self.used_insults) > 10:
                    self.used_insults.pop(0)

    def new_round(self) -> None:
        self.round_number += 1
        self.round_over = False
        self.anger = self.start
        self.steps.clear()


class SessionStore:
    """Tiny in-memory store with TTL and hard cap."""

    def __init__(self, ttl: int = 3 * 3600, limit: int = 200):
        self.ttl = ttl
        self.limit = limit
        self._data: dict = {}

    def _prune(self) -> None:
        now = time.time()
        for sid in [k for k, v in self._data.items() if now - v.touched > self.ttl]:
            del self._data[sid]
        if len(self._data) > self.limit:
            oldest = sorted(self._data, key=lambda k: self._data[k].touched)
            for sid in oldest[: len(self._data) - self.limit]:
                del self._data[sid]

    def get(self, sid: str, start: int) -> Session:
        self._prune()
        session = self._data.get(sid)
        if session is None or session.start != start:
            session = Session(start)
            self._data[sid] = session
        return session

    def find(self, sid: str) -> Optional[Session]:
        session = self._data.get(sid)
        return session if session else None
