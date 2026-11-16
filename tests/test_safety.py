"""Smoke tests for the safety keyword net (phase 0)."""

import safety


def test_self_harm_english():
    for text in [
        "I want to kill myself",
        "honestly I want to die",
        "I keep thinking about suicide",
        "I'd be better off dead",
    ]:
        assert safety.check(text) == "self", text


def test_self_harm_manglish():
    for text in [
        "enikku marikkan thonnunnu",
        "njan chathu pokanam",
        "jeevikkan vayya da",
    ]:
        assert safety.check(text) == "self", text


def test_self_harm_malayalam_script():
    for text in ["എനിക്ക് ജീവിക്കണ്ട", "ആത്മഹത്യ ചെയ്യാൻ തോന്നുന്നു", "ഞാൻ മരിക്കണം"]:
        assert safety.check(text) == "self", text


def test_harm_to_others():
    for text in ["I will kill him", "ninne kollum", "അവനെ കൊല്ലണം"]:
        assert safety.check(text) == "other", text


def test_normal_venting_is_not_flagged():
    """Angry venting must not trigger the crisis reply."""
    for text in [
        "This deadline is killing me",
        "I want to kill this report",
        "I'm dying of laughter",
        "My boss murdered my idea",
        "This day is dead",
        "chaa da, enthaa ithu",
    ]:
        assert safety.check(text) is None, text


def test_reply_is_out_of_character_and_has_helpline():
    text = safety.reply("en")
    assert "not the character" in text
    assert "14416" in text
    assert "not a therapist" in text


def test_reply_language():
    assert safety.reply("ml") != safety.reply("en")
    assert "14416" in safety.reply("ml")
    assert safety.reply("manglish") == safety.reply("en")


def test_empty_input():
    assert safety.check("") is None
    assert safety.check("   ") is None
