from trade_journal import TradeJournal


def _trade(position_id, pnl):
    return {
        "position_id": position_id,
        "symbol": "NIFTY",
        "strategy": "OPENING_RANGE_BREAKOUT",
        "side": "LONG",
        "entry_price": 100,
        "exit_price": 101,
        "quantity": 1,
        "pnl": pnl,
        "exit_reason": "TEST",
        "entry_time": "2026-08-26T09:30:00+05:30",
        "exit_time": "2026-08-26T10:00:00+05:30",
    }


def test_trade_journal_survives_restart_and_clear(tmp_path):
    path = tmp_path / "journal.jsonl"
    first = TradeJournal(path)
    first.record_trade(_trade("one", 100))
    first.record_trade(_trade("two", -40))

    restored = TradeJournal(path)
    assert len(restored.get_all_trades()) == 2
    assert restored.analyze()["summary"]["total_pnl"] == 60
    assert restored.clear() == 2
    assert TradeJournal(path).get_all_trades() == []


def test_strategy_breakdown_includes_profit_factor(tmp_path):
    journal = TradeJournal(tmp_path / "journal.jsonl")
    journal.record_trade(_trade("one", 120))
    journal.record_trade(_trade("two", -40))
    stats = journal.analyze()["by_strategy"]["OPENING_RANGE_BREAKOUT"]
    assert stats["profit_factor"] == 3.0
