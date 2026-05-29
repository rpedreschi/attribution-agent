"""The canonical dataset must stay internally consistent — these guard it."""
from attribution_agent import sample_data as sd


def test_invariants_hold():
    sd.validate()  # raises AssertionError if any tie-out breaks


def test_all_three_models_sum_to_total():
    for model in ("last_touch", "linear", "time_decay"):
        assert sum(sd.revenue_for_model(model).values()) == sd.TOTAL_ATTRIBUTED_REVENUE


def test_deals_and_spend_tie_out():
    assert sum(c.attributed_deals for c in sd.CHANNELS) == sd.TOTAL_WON_DEALS
    assert sd.total_spend() == 1_900_000


def test_funnel_rolls_up():
    assert sum(f.won for f in sd.FUNNEL) == sd.TOTAL_WON_DEALS
    assert sum(f.opps for f in sd.FUNNEL) == sd.TOTAL_OPPORTUNITIES
