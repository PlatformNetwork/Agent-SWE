import pytest

from epymorph.adrio import cdc
from epymorph.adrio.adrio import ADRIOContextError
from epymorph.geography.custom import CustomScope
from epymorph.geography.us_census import StateScope
from epymorph.time import TimeFrame


def test_influenza_state_hosp_daily_invalid_column():
    with pytest.raises(ValueError):
        cdc.InfluenzaStateHospitalizationDaily(column="totals")
    with pytest.raises(ValueError):
        cdc.InfluenzaStateHospitalizationDaily(column="admission")


def test_influenza_state_hosp_daily_context_validation():
    adrio = cdc.InfluenzaStateHospitalizationDaily(column="admissions")
    with pytest.raises(ADRIOContextError):
        adrio.with_context(
            scope=CustomScope(["A", "B"]),
            time_frame=TimeFrame.range("2021-01-01", "2021-01-03"),
        ).evaluate()

    with pytest.raises(ADRIOContextError):
        adrio.with_context(
            scope=StateScope.in_states(["AZ", "CA"], year=2019),
            time_frame=TimeFrame.range("2019-01-01", "2019-01-03"),
        ).evaluate()
