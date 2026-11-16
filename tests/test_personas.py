"""Content checks for the per-language characters (phase 4)."""

import personas

LANGS = ("en", "manglish", "ml")


def test_every_mode_has_three_openers():
    for key, cfg in personas.MODES.items():
        for lang in LANGS:
            assert cfg["openers"].get(lang, "").strip(), f"{key}/{lang} has no opener"


def test_every_mode_has_spoken_examples():
    for key, cfg in personas.MODES.items():
        for lang in LANGS:
            assert len(cfg["style"].get(lang, [])) >= 3, f"{key}/{lang} needs three lines"


def test_opener_differs_per_language():
    for key, cfg in personas.MODES.items():
        assert len({cfg["openers"][lang] for lang in LANGS}) == 3, f"{key} repeats an opener"


def test_prompt_uses_the_selected_language_examples():
    assert "ഞാൻ വെള്ളിയാഴ്ച" in personas.system_prompt("boss", 2, "ml", 9)
    assert "Njan Friday" in personas.system_prompt("boss", 2, "manglish", 9)
    assert "I asked for it on Friday" in personas.system_prompt("boss", 2, "en", 9)


def test_malayalam_lines_are_really_in_malayalam_script():
    for key, cfg in personas.MODES.items():
        for line in cfg["style"]["ml"] + [cfg["openers"]["ml"]]:
            assert any("\u0d00" <= ch <= "\u0d7f" for ch in line), f"{key} has a mixed-up line"


def test_unknown_language_falls_back_to_english():
    text = personas.system_prompt("vent", 1, "xx", 0)
    assert "You're allowed to be angry about that." in text


def test_scenarios_point_at_real_characters():
    for key, sc in personas.SCENARIOS.items():
        assert sc["mode"] in personas.MODES, key
        assert sc["goal"].strip() and sc["scene"].strip(), key


def test_scenarios_are_trilingual():
    for key, sc in personas.SCENARIOS.items():
        for lang in LANGS:
            assert sc["openers"].get(lang, "").strip(), f"{key}/{lang}"


def test_scene_reaches_the_prompt():
    text = personas.system_prompt("boss", 2, "en", 9, scene="The user is asking for leave.")
    assert "The user is asking for leave." in text


def test_new_characters_exist():
    for key in ("amma", "friend", "coworker", "customer"):
        assert key in personas.MODES, key


def test_default_backend_matches_key_availability():
    """Cloud is the default only when a real key is configured; a .env placeholder
    must never be sent to Google (that caused the 'API key not valid' error)."""
    import main

    cfg = main.get_config()
    assert cfg["default_provider"] == ("gemini" if main.GEMINI_KEY else "ollama")
    assert cfg["gemini_available"] is bool(main.GEMINI_KEY)
    assert not main.GEMINI_KEY.startswith("your_")
