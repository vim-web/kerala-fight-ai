"""Smoke tests for the phase 1 anger arc (pure logic, no server)."""

import anger
import personas


def test_specific_calm_reply_lowers_a_lot():
    text = "I sent it on Friday because the client changed the scope. I should have flagged it earlier."
    assert anger.step(text) == -3  # clamped at the per-turn maximum


def test_apology_counts_more_than_plain_text():
    assert anger.step("sorry, my mistake") == -2
    assert anger.step("check the file again") == -1


def test_short_effort_barely_helps():
    assert anger.step("ok") == 0
    assert anger.step("hmmm") == 0


def test_pure_insult_raises_anger():
    assert anger.step("you useless idiot") >= 1
    assert anger.step("this is fucking nonsense, you are useless") >= 1


def test_length_alone_is_not_enough_to_max_out():
    text = "a" * 0 + "I was at the office the whole day and the network was down again"
    assert anger.step(text) == -2  # length + specific, no apology


def test_repetition_does_not_lower():
    previous = ["I sent it on Friday because the client changed the scope and I should have flagged it"]
    assert anger.step(previous[0], previous) == 0


def test_spam_does_not_lower():
    for text in ["asdfasdf", "!!!!!", "aaaaaaaa", "hmmm", ""]:
        assert anger.step(text) == 0, text


def test_malayalam_text_is_not_treated_as_spam():
    text = "ഞാൻ ഇന്ന് വളരെ ക്ഷമയോടെ പറഞ്ഞതാണ്, അവൻ കേട്ടില്ല"
    assert anger.step(text) <= -1


def test_anger_is_clamped():
    assert anger.apply(0, -3) == 0
    assert anger.apply(10, 2) == 10
    assert anger.apply(9, -3) == 6


def test_judge_bonus_is_small():
    assert anger.judge_bonus({"user_calm": 9, "addressed_point": True}) == -1
    assert anger.judge_bonus({"user_calm": 2}) == 1
    assert anger.judge_bonus({"user_calm": 5, "addressed_point": True}) == 0
    assert anger.judge_bonus(None) == 0
    assert anger.judge_bonus({}) == 0
    assert anger.judge_bonus({"user_calm": "junk"}) == 0


def test_calm_score_for_a_good_session():
    result = anger.calm_score(9, 0, [-3, -2, -2, -2])
    assert result["score"] >= 70
    assert result["label"] == "Very calm"
    assert result["calmer"] is True


def test_calm_score_for_a_stuck_session():
    result = anger.calm_score(9, 9, [1, 1, 1])
    assert result["score"] < 40
    assert result["label"] == "Still tense"
    assert result["calmer"] is False


def test_calm_score_without_an_anger_meter():
    result = anger.calm_score(0, 0, [-2, -2])
    assert result["calmer"] is None
    assert 0 <= result["score"] <= 100


def test_session_store_keeps_state_and_resets_on_mode_change():
    store = anger.SessionStore()
    session = store.get("aaaa1111", 9)
    assert session.anger == 9
    session.turn(-2)
    assert store.get("aaaa1111", 9).anger == 7
    assert store.get("aaaa1111", 8).anger == 8  # different mode -> fresh
    assert store.find("nosuchid") is None


def test_fight_mode_never_apologizes_at_zero_anger():
    prompt = personas.system_prompt("boss", 2, "en", 0).lower()
    assert "apologise" not in prompt
    assert "refusing to back down" in prompt or "fight intensity" in prompt


def test_practice_mode_asks_for_an_apology_at_zero_anger():
    prompt = personas.system_prompt("coworker", 2, "en", 0).lower()
    assert "apologise" in prompt


def test_win_detection():
    assert anger.is_win("i win")
    assert anger.is_win("I WIN")
    assert anger.is_win("njan jayichu")
    assert anger.is_win("ഞാൻ ജയിച്ചു")
    assert not anger.is_win("hello da myre")


def test_every_prompt_formats():
    for mode in personas.MODES:
        for level in (0, 5, 10):
            text = personas.system_prompt(mode, 3, "ml", level)
            assert text and "{" not in text
