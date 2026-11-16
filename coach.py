"""Split the coach's plain-text reply into parts the page can lay out.

The local model writes prose, not JSON, so we read back the headings it was
asked for. Nothing is invented: a missing heading just leaves that part empty,
and the original text is always kept so the page can fall back to it.
"""

import re

HEADS = (
    ("worked", ("what worked", "what went well", "what you did well", "what helped")),
    ("hurt", ("what hurt you", "what hurt", "what went wrong", "what to try", "what to change")),
    ("better", ("a better reply", "better reply", "try saying", "instead you could say")),
)

# "- point", "* point", "1. point", "• point" all mean the same thing.
_BULLET = re.compile(r"^(?:[-*\u2022\u00b7]|\d+[.)])\s*")
# The model likes to write "2 points - ..." inside the heading line.
_POINTS = re.compile(r"^\d+\s*(?:points?|pts?)\b\s*(?:[-:\u2014]\s*)?", re.IGNORECASE)
_SCORE = re.compile(r"(\d{1,2})\s*(?:/|out of)\s*10", re.IGNORECASE)
# "A better reply you could have used: ..." leaves the lead-in behind.
_BETTER_LEAD = re.compile(
    r"^(?:you\s+)?(?:could\s+have\s+(?:used|said)|could\s+say|might\s+have\s+said|"
    r"should\s+have\s+said|might\s+say)\s*[:-\u2014]?\s*",
    re.IGNORECASE,
)
# The prompt asks for a closing remark on calmness; the page shows that separately,
# so it must not end up inside the suggested quote.
_CALM_TAIL = re.compile(r"\s+(?=(?:Overall,?\s+)?you\s+(?:seem|sound|appear)\b)", re.IGNORECASE)
_TRIM = " \t:-—\u2022\u00b7*#"
_MAX_ITEMS = 3
_MAX_ITEM = 300
_MAX_BETTER = 400


def _heading(line: str):
    """Return (kind, rest) when the line opens a section, else (None, line)."""
    probe = line.lstrip()
    while probe[:1] in ("*", "#", "-", " "):
        probe = probe[1:]
    low = probe.lower()
    for kind, names in HEADS:
        for name in names:
            if not low.startswith(name):
                continue
            after = low[len(name):]
            if after[:1] not in ("", ":", " ", "-", "\u2014"):
                continue  # "what works" is not "what worked"
            return kind, probe[len(name):].lstrip(_TRIM).strip()
    return None, line


def _push(parts: dict, kind: str, text: str) -> None:
    text = _POINTS.sub("", (text or "").strip(_TRIM)).strip(_TRIM)
    if not text or len(parts[kind]) >= _MAX_ITEMS:
        return
    if text.rstrip(".").lower() in {"none", "nothing", "n/a", "na"}:
        return
    if text.lower() in {item.lower() for item in parts[kind]}:
        return
    parts[kind].append(text[:_MAX_ITEM])


def sections(text: str) -> dict:
    """Best-effort structure for one coaching reply. Never raises."""
    raw = (text or "").strip()
    parts = {"score": None, "worked": [], "hurt": [], "better": "", "text": raw}

    match = _SCORE.search(raw)
    if match:
        parts["score"] = max(0, min(10, int(match.group(1))))

    current = None
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        kind, rest = _heading(line)
        if kind:
            current = kind
            if rest:
                if kind == "better":
                    parts["better"] = rest[:_MAX_BETTER]
                else:
                    _push(parts, kind, _BULLET.sub("", rest))
            continue
        if current == "better":
            if len(parts["better"]) < _MAX_BETTER:
                parts["better"] = (parts["better"] + " " + line).strip()[:_MAX_BETTER]
        elif current in ("worked", "hurt"):
            _push(parts, current, _BULLET.sub("", line).strip(_TRIM))

    parts["better"] = _BETTER_LEAD.sub("", parts["better"]).strip(_TRIM)
    parts["better"] = _CALM_TAIL.split(parts["better"], maxsplit=1)[0].strip(_TRIM)
    return parts
