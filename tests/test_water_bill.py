from decimal import Decimal
import pytest
from section_01_technical.backend.water_bill import (
    WaterBillingService,
    consumption,
    estimated_consumption,
    calculate_bill,
    configured_tariff,
    Tariff,
    TariffBand,
)


@pytest.mark.parametrize(
    "units,expected", [(0, "200"), (10, "700"), (11, "775"), (30, "2200"), (31, "2310")]
)
def test_boundaries(units, expected):
    assert calculate_bill(units, configured_tariff()) == Decimal(expected)


def test_rollover():
    assert consumption(99990, 15, rollover=True) == 25


def test_estimation_preserves_precision():
    assert WaterBillingService().bill(actual_consumptions=[10, 10, 11])[
        "amount"
    ] == Decimal("725.00")


def test_missing_history():
    with pytest.raises(ValueError):
        estimated_consumption([10, 20])


def test_missing_reading():
    with pytest.raises(ValueError):
        WaterBillingService().bill(previous=1)


@pytest.mark.parametrize(
    "previous,current,digits,rollover",
    [
        (-1, 2, 5, False),
        (1, 100000, 5, False),
        (20, 10, 5, False),
        (10, 20, 5, True),
        (1, 2, 0, False),
    ],
)
def test_invalid_reading(previous, current, digits, rollover):
    with pytest.raises(ValueError):
        consumption(previous, current, digits, rollover)


def test_invalid_tariff():
    with pytest.raises(ValueError):
        calculate_bill(10, Tariff(Decimal(200), [TariffBand(Decimal(10), Decimal(50))]))


def test_configuration_changes_amount():
    assert calculate_bill(
        1, Tariff(Decimal(5), [TariffBand(None, Decimal(7))])
    ) == Decimal(12)


def test_estimation_excludes_estimated_and_uses_latest_actual():
    readings = [
        {"reading_type": "ACTUAL", "reading_date": i, "reading_value": v}
        for i, v in enumerate([0, 100, 110, 130, 160])
    ]
    readings.append(
        {"reading_type": "ESTIMATED", "reading_date": 99, "reading_value": 900}
    )
    assert WaterBillingService().estimate_from_readings(readings)["consumption"] == 20


def test_database_estimation_missing_history():
    with pytest.raises(ValueError):
        WaterBillingService().estimate_from_readings([])
