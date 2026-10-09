import math
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from app.model import analyze, probabilities, summarize_detailed
from conftest import make_fixture


@pytest.mark.parametrize("home,away", [(0.15,0.2),(1.2,1.4),(4,0.5),(15,15)])
def test_probability_partitions(home, away):
    p=probabilities(home,away)
    assert all(0 <= value <= 1+1e-12 for value in p.values())
    assert p["home"]+p["draw"]+p["away"] == pytest.approx(1)
    for line in ("1.5","2.5","3.5"):
        assert p[f"over_{line}"]+p[f"under_{line}"] == pytest.approx(1)
    assert p["btts_yes"]+p["btts_no"] == pytest.approx(1)
    assert p["over_1.5"] >= p["over_2.5"] >= p["over_3.5"]


def test_symmetric_teams_and_analytic_btts():
    p=probabilities(1.5,1.5)
    assert p["home"] == pytest.approx(p["away"])
    assert p["btts_yes"] == pytest.approx((1-math.exp(-1.5))**2)


def test_stronger_attack_has_higher_win_probability():
    assert probabilities(2,1)["home"] > probabilities(1,1)["home"]


def test_no_fake_probabilities_when_data_missing(fixture):
    result=analyze(fixture,[])
    assert result["probabilities"] is None
    assert result["confidence"] == "insuficiente"


def test_model_real_input_sample_and_sensitivity(fixture,history):
    result=analyze(fixture,history)
    assert result["confidence"] == "moderada"
    assert result["sample"] == {"league":120,"home_venue":10,"away_venue":10}
    assert all(result["sensitivity_low"][k] <= v+1e-12 for k,v in result["probabilities"].items())
    assert result["home_recent"]["sample"] == 10


def test_future_incomplete_and_other_season_do_not_leak(fixture,history):
    baseline=analyze(fixture,history)
    future=make_fixture(500,1,2,(10,0),datetime.now(timezone.utc)+timedelta(days=5),"FT")
    incomplete=make_fixture(501,1,2,(None,None),datetime.now(timezone.utc)-timedelta(days=2),"FT")
    wrong_season=deepcopy(history[0]); wrong_season["league"]["season"]=2025; wrong_season["goals"]["home"]=50
    extra_time=make_fixture(502,1,2,(10,0),datetime.now(timezone.utc)-timedelta(days=2),"AET")
    assert analyze(fixture,history+[future,incomplete,wrong_season,extra_time])["probabilities"] == baseline["probabilities"]


def test_null_detailed_stats_remain_unknown():
    payloads=[{"response":[{"team":{"id":1},"statistics":[{"type":"Corner Kicks","value":None},{"type":"Yellow Cards","value":2},{"type":"Red Cards","value":0}]}]}]
    result=summarize_detailed(payloads,1)
    assert result["corners"] == {"mean":None,"sample":0}
    assert result["red_cards"] == {"mean":0,"sample":1}
