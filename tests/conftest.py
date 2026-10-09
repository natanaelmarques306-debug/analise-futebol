"""Dados sintéticos exclusivos dos testes; nunca enviados ao painel em produção."""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.storage import Store


def make_fixture(identifier=999, home=1, away=2, goals=(None, None), kickoff=None, status="NS", league=71, season=2026):
    return {"fixture": {"id": identifier, "date": (kickoff or datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),
                        "status": {"short": status}, "venue": {"name": "Estádio sintético de teste"}},
            "league": {"id": league, "name": "Liga sintética de teste", "country": "Teste", "season": season},
            "teams": {"home": {"id": home, "name": f"Equipe teste {home}"}, "away": {"id": away, "name": f"Equipe teste {away}"}},
            "goals": {"home": goals[0], "away": goals[1]}}


@pytest.fixture
def fixture():
    return make_fixture()


@pytest.fixture
def history():
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(120):
        home, away = (1, 3) if i % 3 == 0 else (4, 2) if i % 3 == 1 else (3, 4)
        rows.append(make_fixture(i, home, away, (i % 4, i % 3), now-timedelta(days=i+1), "FT"))
    return rows


@pytest.fixture
def store(tmp_path):
    db=Store(str(tmp_path / "test.sqlite3"))
    yield db
    db.close()


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, api_football_key="test-only-key", database_path=str(tmp_path/"test.sqlite3"), days_ahead=0)
