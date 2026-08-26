import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orb_research import optimize_orb


def test_optimizer_rejects_short_history():
    assert optimize_orb([])["status"] == "INSUFFICIENT_DATA"
