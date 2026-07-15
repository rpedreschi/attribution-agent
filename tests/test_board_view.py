"""The dashboard board-view contract must stay stable for the UI to bind to."""
from attribution_agent.agent.reporting import BoardPackData
from attribution_agent.api.board_view import build_board_view, snapshot_of


def _view(**kw):
    d = BoardPackData.from_sample()
    return d, build_board_view(d, excluded_channels=["Brand", "Events", "AI Assistant"], **kw)


def test_top_level_shape():
    _d, v = _view()
    assert set(v) == {"meta", "live_board", "model_compare", "reallocation_agent",
                      "decision_ledger"}
    assert {"kpis", "what_changed", "money_by_channel"} <= set(v["live_board"])
    assert {"credit_by_channel", "credit_by_campaign", "incrementality_tests"} \
        <= set(v["model_compare"])


def test_influenced_exceeds_sourced_and_never_summed():
    _d, v = _view()
    kpis = {k["key"]: k for k in v["live_board"]["kpis"]}
    assert kpis["influenced"]["value"] > kpis["sourced_pipeline"]["value"]
    assert kpis["influenced"]["subtext"] == "held separate, never summed"


def test_credit_shares_normalize_per_model():
    _d, v = _view()
    rows = v["model_compare"]["credit_by_channel"]
    for model in ("last_touch", "linear", "time_decay"):
        # shares are rounded to 4dp for the UI; tolerate the rounding drift
        assert abs(sum(r["shares"][model] for r in rows) - 1.0) < 5e-3
    # every row carries a disagreement verdict
    assert all(r["status"] in {"agree", "disagree", "thin"} for r in rows)


def test_ai_slip_and_thin_cards_are_real():
    _d, v = _view()
    cards = v["live_board"]["what_changed"]
    assert any(c["kind"] == "drift" and c["real"] for c in cards)  # share-of-model slip
    # illustrative sections are flagged, not passed off as measured
    assert v["model_compare"]["incrementality_tests"]["illustrative"] is True


def test_what_changed_diffs_against_prior_snapshot():
    d = BoardPackData.from_sample()
    prev = snapshot_of(d)
    # perturb one channel so the mover card fires
    prev["by_channel_td"]["Paid Search"] = d.channel_attr("Paid Search").time_decay - 50_000
    v = build_board_view(d, prev_snapshot=prev,
                         excluded_channels=["Brand", "Events", "AI Assistant"])
    titles = [c["title"] for c in v["live_board"]["what_changed"]]
    assert any("moved since your last look" in t for t in titles)


def test_ledger_has_agent_and_human_events():
    d = BoardPackData.from_sample()
    decisions = [{"ts": "2026-07-15T10:00:00", "decision": "approve",
                  "action": "Increase", "channel": "Email Nurture", "reason": "ok"}]
    v = build_board_view(d, decisions=decisions,
                         excluded_channels=["Brand", "Events", "AI Assistant"])
    actors = {e["actor"] for e in v["decision_ledger"]}
    assert {"AGENT", "HUMAN"} <= actors
    assert v["reallocation_agent"]["autonomy"]["match_rate"] == {"matched": 1, "of": 1}
