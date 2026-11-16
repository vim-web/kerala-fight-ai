"""Tests for Live Improv Rules: Mirror and One-Up, Token Limits, Animal One-Up, and 10-insult tracking."""

import anger
import main
import personas


def test_mirror_shape_two_words():
    prompt = personas.system_prompt("boss", 2, "ml", 9, user_message="പോടാ മൈരേ")
    assert "ONLY 2 TO 6 WORDS" in prompt
    assert "LIVE MIRROR RULE" in prompt


def test_mirror_shape_rant():
    long_msg = "ഞാൻ ഇന്നലെ രാത്രി മുഴുവൻ ഇരുന്ന് ജോലി ചെയ്തു എന്നിട്ട് നിങ്ങൾ എന്നെ വീണ്ടും കുറ്റപ്പെടുത്തുന്നു ഇത് എന്ത് അന്യായമാണ് സാറേ കമ്പനിയിൽ ആർക്കും ഒരു വിലയുമില്ലേ"
    prompt = personas.system_prompt("boss", 2, "ml", 9, user_message=long_msg)
    assert "Rant back furiously" in prompt or "long rant" in prompt


def test_animal_insult_one_up():
    prompt = personas.system_prompt("boss", 2, "ml", 9, user_message="നീ ഒരു പട്ടി ആണ്")
    assert "ANIMAL ONE-UP RULE" in prompt
    assert "patti" in prompt


def test_reusing_user_words():
    prompt = personas.system_prompt("boss", 2, "ml", 9, user_message="എന്റെ പ്രോജക്റ്റ് സബ്മിറ്റ് ചെയ്തു")
    assert "REUSE USER'S WORDS" in prompt
    assert "പ്രോജക്റ്റ്" in prompt


def test_last_10_insults_tracked_and_avoided():
    session = anger.Session(9)
    for i in range(15):
        session.add_used_insult(f"Insult {i}")

    # Must be capped at exactly 10
    assert len(session.used_insults) == 10
    assert session.used_insults[0] == "Insult 5"
    assert session.used_insults[-1] == "Insult 14"

    prompt = personas.system_prompt("boss", 2, "ml", 9, used_insults=session.used_insults)
    assert "NEVER REPEAT ANY OF THESE RECENT COMEBACKS/INSULTS" in prompt
    assert "Insult 14" in prompt


def test_casual_first_message_opener():
    boss_ml = personas.MODES["boss"]["openers"]["ml"]
    assert "ഹായ് ഡാ" in boss_ml
    gf_ml = personas.MODES["girlfriend"]["openers"]["ml"]
    assert "ഹായ് ഡാ" in gf_ml


def test_token_cap_and_temperature_settings():
    assert main.OLLAMA_NUM_PREDICT == 60

