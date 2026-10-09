import math
from datetime import datetime, timedelta, timezone

from app.model import parse_time

MARKETS = {
    "Match Winner": ({"Home": "home", "Draw": "draw", "Away": "away"}, [{"home", "draw", "away"}]),
    "Goals Over/Under": ({f"{direction} {line}": f"{direction.lower()}_{line}"
                          for line in ("1.5", "2.5", "3.5") for direction in ("Over", "Under")},
                         [{f"over_{line}", f"under_{line}"} for line in ("1.5", "2.5", "3.5")]),
    "Both Teams Score": ({"Yes": "btts_yes", "No": "btts_no"}, [{"btts_yes", "btts_no"}]),
    # Dupla chance tem resultados sobrepostos: não normalizamos a margem.
    "Double Chance": ({"Home/Draw": "home_draw", "Draw/Away": "away_draw", "Home/Away": "home_away"}, []),
}
LABELS = {"home": "Vitória da casa", "draw": "Empate", "away": "Vitória visitante",
          "btts_yes": "Ambas marcam — sim", "btts_no": "Ambas marcam — não",
          "home_draw": "Casa ou empate", "away_draw": "Visitante ou empate", "home_away": "Casa ou visitante"}
for line in ("1.5", "2.5", "3.5"):
    LABELS[f"over_{line}"] = f"Mais de {line.replace('.', ',')} gols"
    LABELS[f"under_{line}"] = f"Menos de {line.replace('.', ',')} gols"


def compare_odds(payload: dict, analysis: dict, max_age_minutes: int, now: datetime | None = None) -> list[dict]:
    if not analysis.get("probabilities"):
        return []
    now = now or datetime.now(timezone.utc)
    opportunities = []
    for entry in payload.get("response", []):
        try:
            updated = parse_time(entry["update"])
            if updated.tzinfo is None or updated > now + timedelta(minutes=5) or now-updated > timedelta(minutes=max_age_minutes):
                continue
        except (KeyError, ValueError, TypeError):
            continue
        for bookmaker in entry.get("bookmakers", []):
            for bet in bookmaker.get("bets", []):
                specification = MARKETS.get(bet.get("name"))
                if not specification:
                    continue
                mapping, groups = specification
                quotes = {}
                for quote in bet.get("values", []):
                    market = mapping.get(quote.get("value"))
                    try:
                        odd = float(quote["odd"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if market and math.isfinite(odd) and odd > 1:
                        quotes[market] = odd
                for market, odd in quotes.items():
                    probability = analysis["probabilities"][market]
                    low = analysis["sensitivity_low"][market]
                    group = next((g for g in groups if market in g and g.issubset(quotes)), None)
                    implied_sum = sum(1/quotes[k] for k in group) if group else None
                    expected = probability * odd - 1
                    conservative = low * odd - 1
                    classification = ("vantagem na sensibilidade" if conservative > 0 and analysis["confidence"] == "moderada"
                                      else "vantagem frágil" if expected > 0 else "sem vantagem")
                    opportunities.append({"market": market, "label": LABELS[market], "odd": odd,
                                          "bookmaker": bookmaker.get("name", "Fornecedor não informado"),
                                          "bookmaker_id": bookmaker.get("id"),
                                          "probability": probability, "fair_odd": 1/probability if probability > 0 else None,
                                          "implied_probability": 1/odd,
                                          "no_vig_probability": (1/odd)/implied_sum if implied_sum else None,
                                          "overround": implied_sum-1 if implied_sum else None,
                                          "expected_value": expected, "sensitivity_ev": conservative,
                                          "confidence": analysis["confidence"], "classification": classification,
                                          "updated_at": updated.isoformat()})
    return sorted(opportunities, key=lambda x: (x["classification"] == "vantagem na sensibilidade", x["sensitivity_ev"], x["expected_value"]), reverse=True)
