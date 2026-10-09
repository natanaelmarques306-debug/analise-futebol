import pytest
from pydantic import ValidationError

from app.config import Settings


def test_leagues_deduplicated_and_blank_optional_id():
    settings=Settings(_env_file=None,league_ids='71, 39,71',preferred_bookmaker_id='')
    assert settings.leagues==[71,39]
    assert settings.preferred_bookmaker_id is None


@pytest.mark.parametrize('fields',[{'league_ids':''},{'league_ids':'0'},{'league_ids':'71,abc'},{'days_ahead':8},{'refresh_minutes':1},{'preferred_bookmaker_id':-1}])
def test_invalid_limits_and_filters_fail_configuration(fields):
    with pytest.raises(ValidationError):
        Settings(_env_file=None,**fields)
