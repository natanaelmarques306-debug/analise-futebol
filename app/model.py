"""Modelo Poisson inicial, exclusivamente alimentado por partidas reais concluídas.

Não é calibrado por backtest. Confiança descreve cobertura da amostra, não acerto.
"""
import math
from datetime import datetime

MODEL_VERSION = "poisson-venue-decay-v1"


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def completed_before(rows: list[dict], kickoff: str) -> list[dict]:
    cutoff = parse_time(kickoff)
    result = []
    for row in rows:
        try:
            if (row["fixture"]["status"]["short"] == "FT"
                    and parse_time(row["fixture"]["date"]) < cutoff
                    and number(row["goals"]["home"]) is not None
                    and number(row["goals"]["away"]) is not None):
                result.append(row)
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(result, key=lambda row: parse_time(row["fixture"]["date"]), reverse=True)


def poisson(rate: float, max_goals: int = 40) -> list[float]:
    if not math.isfinite(rate) or rate <= 0 or rate > 15:
        raise ValueError("Taxa fora do intervalo suportado pelo modelo")
    values = [math.exp(-rate)]
    for k in range(1, max_goals + 1):
        values.append(values[-1] * rate / k)
    mass = sum(values)
    return [v / mass for v in values]


def probabilities(home_rate: float, away_rate: float) -> dict[str, float]:
    home, away = poisson(home_rate), poisson(away_rate)
    win = draw = lose = over15 = over25 = over35 = btts = 0.0
    for i, ph in enumerate(home):
        for j, pa in enumerate(away):
            p = ph * pa
            if i > j: win += p
            elif i == j: draw += p
            else: lose += p
            if i + j > 1.5: over15 += p
            if i + j > 2.5: over25 += p
            if i + j > 3.5: over35 += p
            if i > 0 and j > 0: btts += p
    return {"home": win, "draw": draw, "away": lose,
            "over_1.5": over15, "under_1.5": 1-over15,
            "over_2.5": over25, "under_2.5": 1-over25,
            "over_3.5": over35, "under_3.5": 1-over35,
            "btts_yes": btts, "btts_no": 1-btts,
            "home_draw": win+draw, "away_draw": lose+draw, "home_away": win+lose}


def weighted_rate(rows: list[dict], goal_side: str, baseline: float) -> float:
    # Meia-vida de 5 jogos; regularização equivalente a 3 jogos da própria liga.
    weights = [0.5 ** (i / 5) for i in range(len(rows))]
    numerator = sum(w * row["goals"][goal_side] for w, row in zip(weights, rows))
    return (numerator + 3 * baseline) / (sum(weights) + 3)


def team_summary(rows: list[dict], team: int) -> dict:
    games = [r for r in rows if team in (r["teams"]["home"]["id"], r["teams"]["away"]["id"])][:10]
    form, scored, conceded = [], [], []
    for row in games:
        side = "home" if row["teams"]["home"]["id"] == team else "away"
        other = "away" if side == "home" else "home"
        a, b = row["goals"][side], row["goals"][other]
        scored.append(a); conceded.append(b)
        form.append("V" if a > b else "E" if a == b else "D")
    return {"sample": len(games), "form": form, "goals_for": sum(scored)/len(games) if games else None,
            "goals_against": sum(conceded)/len(games) if games else None,
            "fixture_ids": [r["fixture"]["id"] for r in games]}


def analyze(fixture: dict, history: list[dict]) -> dict:
    # Histórico da mesma liga e temporada; exclui qualquer jogo depois do início.
    rows = completed_before(history, fixture["fixture"]["date"])
    rows = [r for r in rows if r["league"]["id"] == fixture["league"]["id"]
            and r["league"]["season"] == fixture["league"]["season"]]
    home_id, away_id = fixture["teams"]["home"]["id"], fixture["teams"]["away"]["id"]
    home_rows = [r for r in rows if r["teams"]["home"]["id"] == home_id][:10]
    away_rows = [r for r in rows if r["teams"]["away"]["id"] == away_id][:10]
    h2h = [r for r in rows if {r["teams"]["home"]["id"], r["teams"]["away"]["id"]} == {home_id, away_id}][:5]
    base = {"model_version": MODEL_VERSION, "home_recent": team_summary(rows, home_id),
            "away_recent": team_summary(rows, away_id),
            "h2h": [{"date": r["fixture"]["date"], "home": r["teams"]["home"]["name"],
                     "away": r["teams"]["away"]["name"], "goals": r["goals"]} for r in h2h],
            "sample": {"league": len(rows), "home_venue": len(home_rows), "away_venue": len(away_rows)},
            "probabilities": None, "rates": None, "confidence": "insuficiente",
            "limitations": ["Modelo inicial sem calibração por backtest; confiança indica cobertura de dados.",
                            "Confrontos diretos, cartões, escanteios e desfalques são contexto; não ajustam o modelo de gols.",
                            "O modelo não controla força individual dos adversários nem mudanças de elenco."]}
    if len(rows) < 40 or min(len(home_rows), len(away_rows)) < 5:
        base["reason"] = "Exige 40 jogos da liga e 5 jogos de cada equipe no respectivo mando nesta temporada."
        return base
    baseline_h = sum(r["goals"]["home"] for r in rows) / len(rows)
    baseline_a = sum(r["goals"]["away"] for r in rows) / len(rows)
    if min(baseline_h, baseline_a) <= 0:
        base["reason"] = "Média da liga inválida para estimativa."
        return base
    rate_h = weighted_rate(home_rows, "home", baseline_h) * weighted_rate(away_rows, "home", baseline_h) / baseline_h
    rate_a = weighted_rate(away_rows, "away", baseline_a) * weighted_rate(home_rows, "away", baseline_a) / baseline_a
    if max(rate_h, rate_a) > 15:
        base["reason"] = "Taxas extremas: confira os dados; análise omitida."
        return base
    base.update(probabilities=probabilities(rate_h, rate_a), rates={"home": rate_h, "away": rate_a},
                confidence="moderada" if min(len(home_rows), len(away_rows)) >= 8 and len(rows) >= 100 else "baixa",
                reason=None)
    # Faixa de sensibilidade, não intervalo estatístico nem garantia de cobertura.
    scenarios = [probabilities(rate_h * h, rate_a * a) for h in (0.85, 1, 1.15) for a in (0.85, 1, 1.15)]
    base["sensitivity_low"] = {k: min(s[k] for s in scenarios) for k in base["probabilities"]}
    return base


def summarize_detailed(payloads: list[dict], team_id: int) -> dict:
    values = {"corners": [], "yellow_cards": [], "red_cards": []}
    keys = {"Corner Kicks": "corners", "Yellow Cards": "yellow_cards", "Red Cards": "red_cards"}
    for payload in payloads:
        for entry in payload.get("response", []):
            if entry.get("team", {}).get("id") != team_id:
                continue
            for stat in entry.get("statistics", []):
                key = keys.get(stat.get("type"))
                value = number(stat.get("value"))
                if key and value is not None:
                    values[key].append(value)
    return {key: {"mean": sum(rows)/len(rows) if rows else None, "sample": len(rows)} for key, rows in values.items()}
