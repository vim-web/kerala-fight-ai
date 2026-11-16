import store


def make(tmp_path):
    return store.Store(tmp_path / "h.db")


def turn(s, sid="sess-12345678", text="I am sorry, I should have called.", reply="Fine.", **kw):
    s.add_turn(sid, mode=kw.get("mode", "boss"), user_text=text, reply=reply, **kw)


def test_turn_is_saved_and_read_back(tmp_path):
    s = make(tmp_path)
    turn(s)
    data = s.get("sess-12345678")
    assert data["mode"] == "boss"
    assert data["turns"] == 1
    assert [m["role"] for m in data["messages"]] == ["user", "ai"]
    assert data["messages"][1]["text"] == "Fine."


def test_unknown_session_returns_none(tmp_path):
    assert make(tmp_path).get("nope-nope") is None


def test_retried_message_does_not_duplicate(tmp_path):
    s = make(tmp_path)
    turn(s, text="Same text", reply="")  # first attempt failed after saving
    turn(s, text="Same text", reply="Hello.")  # user retried
    data = s.get("sess-12345678")
    assert data["turns"] == 1
    assert [m["text"] for m in data["messages"]] == ["Same text", "Hello."]


def test_list_is_newest_first_with_a_preview(tmp_path):
    s = make(tmp_path)
    turn(s, sid="sess-aaaaaaaa", reply="First reply.")
    turn(s, sid="sess-bbbbbbbb", text="Second", reply="Second reply.")
    items = s.list()
    assert [i["id"] for i in items] == ["sess-bbbbbbbb", "sess-aaaaaaaa"]
    assert items[0]["preview"].startswith("Second")
    assert items[0]["turns"] == 1


def test_streak_counts_turns_that_did_not_escalate(tmp_path):
    s = make(tmp_path)
    turn(s, text="one", reply="a", delta=1)
    turn(s, text="two", reply="b", delta=-2)
    turn(s, text="three", reply="c", delta=-3)
    assert s.get("sess-12345678")["streak"] == 2
    assert s.stats()["best_streak"] == 2


def test_delete_one_keeps_the_others(tmp_path):
    s = make(tmp_path)
    turn(s, sid="sess-aaaaaaaa")
    turn(s, sid="sess-bbbbbbbb")
    assert s.delete("sess-aaaaaaaa") == 1
    assert s.get("sess-aaaaaaaa") is None
    assert s.get("sess-bbbbbbbb")["turns"] == 1


def test_clear_removes_everything(tmp_path):
    s = make(tmp_path)
    turn(s, sid="sess-aaaaaaaa")
    turn(s, sid="sess-bbbbbbbb")
    assert s.clear() == 2
    assert s.list() == []
    assert s.stats()["turns"] == 0


def test_export_contains_messages(tmp_path):
    s = make(tmp_path)
    turn(s)
    data = s.export()
    assert data["app"] == "Sparring AI"
    assert data["sessions"][0]["messages"][0]["text"].startswith("I am sorry")


def test_state_survives_a_restart(tmp_path):
    s = make(tmp_path)
    turn(s, text="hello", reply="Fine.", anger=6, delta=-3)
    other = store.Store(tmp_path / "h.db")
    assert other.state("sess-12345678") == {"anger": 6, "turns": 1}


def test_empty_text_is_ignored(tmp_path):
    s = make(tmp_path)
    s.add_turn("sess-12345678", mode="boss", user_text="   ", reply="Hi")
    assert s.list() == []
