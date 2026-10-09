from datetime import datetime, timedelta, timezone

import pytest

from app.odds import compare_odds


def payload(age=0, market="Match Winner", values=None):
    return {"response":[{"update":(datetime.now(timezone.utc)-timedelta(minutes=age)).isoformat(),
                        "bookmakers":[{"name":"Casa sintética de teste", "bets":[{"name":market,"values":values or [
                            {"value":"Home","odd":"2.10"},{"value":"Draw","odd":"3.50"},{"value":"Away","odd":"3.60"}]}]}]}]}


def analysis():
    return {"probabilities":{"home":0.52,"draw":0.26,"away":0.22}, "sensitivity_low":{"home":0.48,"draw":0.20,"away":0.18}, "confidence":"moderada"}


def test_expected_value_fair_odds_and_margin():
    rows=compare_odds(payload(),analysis(),60)
    home=next(row for row in rows if row["market"]=="home")
    assert home["expected_value"] == pytest.approx(0.092)
    assert home["fair_odd"] == pytest.approx(1/0.52)
    assert home["sensitivity_ev"] == pytest.approx(0.008)
    assert home["classification"]=="vantagem na sensibilidade"
    assert sum(row["no_vig_probability"] for row in rows)==pytest.approx(1)
    assert home["overround"]==pytest.approx(1/2.1+1/3.5+1/3.6-1)


def test_stale_missing_and_future_timestamp_are_excluded():
    assert compare_odds(payload(61),analysis(),60)==[]
    assert compare_odds(payload(-10),analysis(),60)==[]
    p=payload(); del p["response"][0]["update"]
    assert compare_odds(p,analysis(),60)==[]


def test_incomplete_market_no_margin_and_invalid_quotes_excluded():
    p=payload(values=[{"value":"Home","odd":"2.1"},{"value":"Away","odd":"NaN"},{"value":"Draw","odd":"1"}])
    rows=compare_odds(p,analysis(),60)
    assert len(rows)==1
    assert rows[0]["no_vig_probability"] is None
    assert rows[0]["overround"] is None


def test_double_chance_does_not_normalize_overlapping_outcomes():
    a={"probabilities":{"home_draw":.78},"sensitivity_low":{"home_draw":.70},"confidence":"moderada"}
    rows=compare_odds(payload(market="Double Chance",values=[{"value":"Home/Draw","odd":"1.4"}]),a,60)
    assert rows[0]["no_vig_probability"] is None


def test_unknown_market_and_missing_model_not_invented():
    assert compare_odds(payload(market="Asian Handicap"),analysis(),60)==[]
    assert compare_odds(payload(),{},60)==[]


def test_low_coverage_cannot_be_classified_as_robust():
    a=analysis();a["confidence"]="baixa"
    row=next(row for row in compare_odds(payload(),a,60) if row["market"]=="home")
    assert row["classification"]=="vantagem frágil"
