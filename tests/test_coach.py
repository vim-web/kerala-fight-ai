"""Tests for the feedback parser (pure text in, parts out; no model call)."""

from coach import sections

FULL = """Score: 7/10
What worked:
- You apologised early instead of defending yourself
- You said what you will do next time
What hurt you:
- You explained the reason before acknowledging the problem
A better reply you could have used: "I should have flagged the delay on Monday. That was on me."
You seem calmer than at the start."""


def test_full_reply_is_split_into_parts():
    parts = sections(FULL)
    assert parts["score"] == 7
    assert len(parts["worked"]) == 2
    assert parts["worked"][0].startswith("You apologised early")
    assert len(parts["hurt"]) == 1
    assert "flagged the delay" in parts["better"]


def test_original_text_is_always_kept():
    assert sections(FULL)["text"] == FULL.strip()


def test_bullet_markers_are_stripped():
    for marker in ("- ", "* ", "1. ", "\u2022 "):
        parts = sections("Score: 5/10\nWhat worked:\n" + marker + "You listened\n")
        assert parts["worked"] == ["You listened"], marker


def test_inline_heading_keeps_the_same_line():
    parts = sections("What worked: You stayed on the point\n")
    assert parts["worked"] == ["You stayed on the point"]


def test_markdown_bold_heading_is_understood():
    parts = sections("**Score: 8/10**\n**What worked:**\n* You asked a question\n")
    assert parts["score"] == 8
    assert parts["worked"] == ["You asked a question"]


def test_missing_score_leaves_it_empty():
    parts = sections("What worked:\n- You tried\n")
    assert parts["score"] is None


def test_score_is_clamped_to_ten():
    assert sections("Score: 14/10")["score"] == 10
    assert sections("Score: 0/10")["score"] == 0


def test_reply_with_no_headings_keeps_text_and_no_parts():
    parts = sections("Honestly that went badly and you should try again.")
    assert parts["score"] is None
    assert parts["worked"] == [] and parts["hurt"] == []
    assert parts["better"] == ""
    assert parts["text"].startswith("Honestly")


def test_alternative_headings_are_recognised():
    parts = sections("What went well:\n- You paused\nWhat to try:\n- Say less\n")
    assert parts["worked"] == ["You paused"]
    assert parts["hurt"] == ["Say less"]


def test_filler_words_are_dropped():
    parts = sections("What worked:\n- None\nWhat hurt you:\n- nothing\n")
    assert parts["worked"] == []
    assert parts["hurt"] == []


def test_point_counts_are_stripped():
    # This is how the local model actually words it.
    parts = sections("What worked: 1 point - You owned it\nWhat hurt you: 2 points - You rushed\n")
    assert parts["worked"] == ["You owned it"]
    assert parts["hurt"] == ["You rushed"]


def test_at_most_three_points_per_section():
    parts = sections("What worked:\n- one\n- two\n- three\n- four\n")
    assert len(parts["worked"]) == 3


def test_multiline_better_reply_is_joined():
    parts = sections(
        "A better reply you could have used: \"I should have told you\non Monday.\"\n"
    )
    assert "I should have told you" in parts["better"]
    assert "on Monday" in parts["better"]


def test_better_reply_drops_the_lead_in():
    parts = sections('A better reply you could have used: "I should have told you on Monday."\n')
    assert parts["better"] == '"I should have told you on Monday."'


def test_calm_remark_does_not_leak_into_the_quote():
    parts = sections('A better reply: "Say it on Monday."\nYou seem calmer than at the start.\n')
    assert parts["better"] == '"Say it on Monday."'


def test_empty_input_is_safe():
    for value in ("", "   ", "\n\n"):
        parts = sections(value)
        assert parts["score"] is None
        assert parts["worked"] == [] and parts["hurt"] == []
