from paper_signal_journal import PaperSignalJournal


def signal(signal_id="SIG-1"):
    return {
        "signal_id": signal_id, "symbol": "NIFTY", "strategy_key": "OPENING_RANGE_BREAKOUT",
        "strategy_name": "ORB", "strategy_type": "DIRECTIONAL", "confidence": 70,
        "timestamp": "2026-08-26T09:30:00+00:00", "legs": [],
    }


def test_signal_and_outcome_persist_across_instances(tmp_path):
    path = tmp_path / "signals.jsonl"
    journal = PaperSignalJournal(path)
    signal_id = journal.record_detected(signal(), "TRENDING_UP", "PAPER_RND", {"sent": True})
    journal.record_outcome(signal_id, "RISK_BLOCKED", {"reason": "Duplicate symbol position"})
    item = PaperSignalJournal(path).recent()[0]
    assert item["paper_status"] == "RISK_BLOCKED"
    assert item["paper_outcome"]["reason"] == "Duplicate symbol position"
    assert item["notification"]["sent"] is True


def test_recent_is_newest_first_and_tolerates_corrupt_lines(tmp_path):
    journal = PaperSignalJournal(tmp_path / "signals.jsonl")
    journal.record_detected(signal("ONE"), "MIXED", "PAPER_MANUAL")
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
    journal.record_detected({**signal("TWO"), "symbol": "BANKNIFTY"}, "MIXED", "PAPER_MANUAL")
    assert [item["signal_id"] for item in journal.recent(1)] == ["TWO"]


def test_duplicate_signal_reuses_inbox_item(tmp_path):
    journal = PaperSignalJournal(tmp_path / "signals.jsonl")
    first = journal.record_detected(signal("ONE"), "TRENDING_UP", "PAPER_RND")
    repeated = journal.record_detected({**signal("TWO")}, "TRENDING_UP", "PAPER_RND")
    assert repeated == first
    assert len(journal.recent()) == 1
