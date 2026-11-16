"""Tests for Fight Game, victory conditions, and dialogue selection."""

import anger
import personas
from characters.dialogues import select_relevant_turns, parse_my_lines


def test_custom_lines_loaded_for_boss_and_girlfriend():
    boss_lines = parse_my_lines("boss")
    assert len(boss_lines) >= 30, f"Expected 30 boss situations, got {len(boss_lines)}"
    
    gf_lines = parse_my_lines("girlfriend")
    assert len(gf_lines) >= 30, f"Expected 30 girlfriend situations, got {len(gf_lines)}"


def test_relevant_turns_selection_prioritizes_custom():
    turns = select_relevant_turns("boss", "ml", "റോഡിൽ ബ്ലോക്ക് ആയിരുന്നു സാറേ")
    assert len(turns) >= 5
    # The first selected should be from user's custom situations
    assert any("റോഡ്" in u or "ബ്ലോക്ക്" in u for u, _ in turns)


def test_win_detection_in_all_three_languages():
    assert anger.is_win("i win")
    assert anger.is_win("I win!")
    assert anger.is_win("ഞാൻ ജയിച്ചു")
    assert anger.is_win("njan jayichu da")
    assert not anger.is_win("enthada nokkunnath")


def test_fight_mode_has_no_cooldown():
    assert personas.MODES["boss"]["cooldown"] is False
    assert personas.MODES["girlfriend"]["cooldown"] is False


def test_round_win_prompt_added_on_victory():
    prompt = personas.system_prompt("boss", 2, "ml", 9, round_win=True)
    assert "CRITICAL: The user declared 'i win'" in prompt


def test_session_round_progression():
    store = anger.SessionStore()
    session = store.get("test_sess_1", 9)
    assert session.round_number == 1
    session.new_round()
    assert session.round_number == 2
    assert session.anger == 9


from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import main


def test_api_chat_win_response():
    client = TestClient(main.app)
    with patch("main._generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "ജയിച്ചെന്നോ? പോയി തുലയ്, നിന്റെ തർക്കുത്തരം കേട്ട് തല പുകഞ്ഞു!"
        
        res = client.post("/api/chat", json={
            "mode": "boss",
            "lang": "ml",
            "messages": [{"role": "user", "text": "ഞാൻ ജയിച്ചു"}]
        })
        assert res.status_code == 200
        data = res.json()
        assert data["round_over"] is True
        assert data["expression"] == "sulking"
        assert "ജയിച്ചെന്നോ" in data["reply"]


def test_api_chat_escalation_on_theri():
    client = TestClient(main.app)
    with patch("main._generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "എന്താടാ വിളിച്ചത്? ശബ്ദം താഴ്ത്തി സംസാരിക്കടാ!"
        
        res = client.post("/api/chat", json={
            "mode": "boss",
            "lang": "ml",
            "messages": [{"role": "user", "text": "പോടാ മൈരേ"}]
        })
        assert res.status_code == 200
        data = res.json()
        assert data["round_over"] is False
        assert data["anger"] >= 9
