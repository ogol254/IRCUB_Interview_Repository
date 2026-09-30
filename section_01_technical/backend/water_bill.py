from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence
from .settings import CONFIG


@dataclass(frozen=True)
class TariffBand:
    upper_limit: Optional[Decimal]
    rate: Decimal


@dataclass(frozen=True)
class Tariff:
    service_charge: Decimal
    bands: Sequence[TariffBand]


def consumption(previous, current, meter_digits=5, rollover=False):
    if not 1 <= meter_digits <= 9:
        raise ValueError("meter digits must be between 1 and 9")
    previous, current = Decimal(previous), Decimal(current)
    capacity = Decimal(10) ** meter_digits
    if (
        not previous.is_finite()
        or not current.is_finite()
        or min(previous, current) < 0
        or max(previous, current) >= capacity
    ):
        raise ValueError("reading outside meter capacity")
    if current < previous and not rollover:
        raise ValueError("lower reading requires confirmed rollover")
    if rollover and current >= previous:
        raise ValueError("rollover requires lower current reading")
    return capacity - previous + current if rollover else current - previous


def estimated_consumption(last_three_actual_consumptions):
    if len(last_three_actual_consumptions) != 3:
        raise ValueError(
            "three actual consumption intervals required (four actual readings)"
        )
    values = [Decimal(v) for v in last_three_actual_consumptions]
    if any(not v.is_finite() or v < 0 for v in values):
        raise ValueError("actual consumption must be finite and nonnegative")
    return sum(values, Decimal(0)) / Decimal(3)


def configured_tariff():
    t = CONFIG["water_tariff"]
    return Tariff(
        Decimal(t["service_charge"]),
        [
            TariffBand(
                Decimal(b["upper_limit"]) if b["upper_limit"] else None,
                Decimal(b["rate"]),
            )
            for b in t["bands"]
        ],
    )


def calculate_bill(units, tariff):
    units = Decimal(units)
    if not units.is_finite() or units < 0:
        raise ValueError("consumption must be finite and nonnegative")
    if (
        tariff.service_charge < 0
        or not tariff.bands
        or tariff.bands[-1].upper_limit is not None
    ):
        raise ValueError("invalid tariff configuration")
    remaining, lower, cost = units, Decimal(0), Decimal(0)
    for index, band in enumerate(tariff.bands):
        if (
            band.rate < 0
            or (band.upper_limit is None and index != len(tariff.bands) - 1)
            or (band.upper_limit is not None and band.upper_limit <= lower)
        ):
            raise ValueError("invalid tariff bands")
        quantity = (
            remaining
            if band.upper_limit is None
            else min(remaining, band.upper_limit - lower)
        )
        cost += quantity * band.rate
        remaining -= quantity
        if band.upper_limit is not None:
            lower = band.upper_limit
    return (cost + tariff.service_charge).quantize(
        Decimal(".01"), rounding=ROUND_HALF_UP
    )


class WaterBillingService:
    def estimate_from_readings(self, readings, digits=5):
        actual = sorted(
            (r for r in readings if r["reading_type"] == "ACTUAL"),
            key=lambda r: r["reading_date"],
        )[-4:]
        if len(actual) != 4 or len({r["reading_date"] for r in actual}) != 4:
            raise ValueError(
                "four distinct actual readings required for three actual intervals"
            )
        intervals = [
            consumption(
                previous["reading_value"],
                current["reading_value"],
                digits,
                current.get("rollover_confirmed", False),
            )
            for previous, current in zip(actual, actual[1:])
        ]
        result = self.bill(actual_consumptions=intervals)
        result["basis"] = "average of latest three actual consumption intervals"
        return result

    def bill(
        self,
        previous=None,
        current=None,
        digits=5,
        rollover=False,
        actual_consumptions=None,
    ):
        if actual_consumptions is not None:
            units = estimated_consumption(actual_consumptions)
        elif previous is None or current is None:
            raise ValueError("previous and current readings required")
        else:
            units = consumption(previous, current, digits, rollover)
        return {
            "consumption": units,
            "amount": calculate_bill(units, configured_tariff()),
        }
