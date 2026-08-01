"""Read-only Area-first pilot data boundary."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .pilot_spot_options import (
    PILOT_AREA_NAMES,
    PILOT_SPOT_OPTIONS_PATH,
    PilotSpotOptionsError,
    load_pilot_spot_options,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PILOT_SPOT_POPULATION_PATH = PROJECT_ROOT / "data/prototype/pilot_spot_population.csv"
SPOT_PROTOTYPE_DATA_UNAVAILABLE = "SPOT_PROTOTYPE_DATA_UNAVAILABLE"
SPOT_POPULATION_HEADERS = (
    "pilot_area_code",
    "spot_option_id",
    "observed_at",
    "current_population_min",
    "current_population_max",
    "forecast_60_population_min",
    "forecast_60_population_max",
    "forecast_180_population_min",
    "forecast_180_population_max",
    "data_status",
    "input_method",
    "source_note",
    "updated_at",
)
_SEOUL_OFFSET = timedelta(hours=9)
_LIMITATIONS = (
    "실제 판매 허용 여부는 현장 확인이 필요합니다.",
    "접근성을 현장에서 확인해야 합니다.",
    "안전성을 현장에서 확인해야 합니다.",
    "카트 정차 가능성을 현장에서 확인해야 합니다.",
    "시간대별 운영 가능성을 현장에서 확인해야 합니다.",
)


class SelectedAreaPilotError(ValueError):
    """Raised when the read-only pilot contract cannot be served safely."""


def _finite_float(value: Decimal) -> float:
    converted = float(value)
    if not math.isfinite(converted) or (value != 0 and converted == 0):
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
    return converted


def _safe_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID") from exc
    if parsed.utcoffset() != _SEOUL_OFFSET:
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
    return parsed.isoformat()


def _safe_source_note(value: str) -> str | None:
    note = value.strip()
    lowered = note.lower()
    if len(note) > 300 or any(
        marker in lowered
        for marker in ("/users/", "file://", "http://", "https://", "api_key", "secret")
    ):
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
    return note or None


def _population_range(
    row: dict[str, str],
    minimum_field: str,
    maximum_field: str,
) -> dict[str, float] | None:
    minimum_text = row[minimum_field]
    maximum_text = row[maximum_field]
    if not minimum_text and not maximum_text:
        return None
    if not minimum_text or not maximum_text:
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
    try:
        minimum = Decimal(minimum_text)
        maximum = Decimal(maximum_text)
    except InvalidOperation as exc:
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID") from exc
    if (
        not minimum.is_finite()
        or not maximum.is_finite()
        or minimum < 0
        or maximum < minimum
    ):
        raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
    return {"min": _finite_float(minimum), "max": _finite_float(maximum)}


def _change(
    current: dict[str, float] | None,
    future: dict[str, float] | None,
) -> tuple[float | None, float | None]:
    if current is None or future is None:
        return None, None
    current_midpoint = (
        Decimal(str(current["min"])) + Decimal(str(current["max"]))
    ) / 2
    future_midpoint = (
        Decimal(str(future["min"])) + Decimal(str(future["max"]))
    ) / 2
    amount = future_midpoint - current_midpoint
    amount_float = _finite_float(amount)
    if current_midpoint == 0:
        return amount_float, None
    return amount_float, _finite_float(amount / current_midpoint)


class AreaDataProvider:
    """Return an explicit no-data view until an approved artifact contract exists."""

    def get(self, area_code: str) -> dict[str, object]:
        if area_code not in PILOT_AREA_NAMES:
            raise SelectedAreaPilotError("AREA_NOT_SUPPORTED")
        return {
            "area_code": area_code,
            "area_name": PILOT_AREA_NAMES[area_code],
            "source": None,
            "availability": "DATA_UNAVAILABLE",
            "freshness": "NO_COMPLETE_SNAPSHOT",
            "observed_at": None,
            "current_population": None,
            "forecast_60": None,
            "forecast_180": None,
            "congestion_level": None,
            "forecast_60_congestion_level": None,
            "forecast_180_congestion_level": None,
            "forecast_60_target_at": None,
            "forecast_180_target_at": None,
            "change_amount_60": None,
            "change_rate_60": None,
            "change_amount_180": None,
            "change_rate_180": None,
        }


class PilotSpotOptionRepository:
    """Join validated static Spot identity with optional PM prototype values."""

    def __init__(
        self,
        *,
        master_path: Path = PILOT_SPOT_OPTIONS_PATH,
        population_path: Path | None = PILOT_SPOT_POPULATION_PATH,
    ) -> None:
        self._master_path = master_path
        self._population_path = population_path

    def _population_rows(
        self,
        identities: tuple[dict[str, str], ...],
    ) -> dict[str, dict[str, object]]:
        path = self._population_path
        if path is None:
            return {}
        if path.is_symlink():
            raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
        if not path.exists():
            return {}
        if not path.is_file():
            raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, strict=True)
                if tuple(reader.fieldnames or ()) != SPOT_POPULATION_HEADERS:
                    raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
                raw_rows = tuple(reader)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID") from exc

        identity_areas = {
            identity["spot_option_id"]: identity["pilot_area_code"]
            for identity in identities
        }
        values: dict[str, dict[str, object]] = {}
        seen_spot_ids: set[str] = set()
        for raw_row in raw_rows:
            if None in raw_row:
                raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
            row = {
                str(key): (value or "").strip()
                for key, value in raw_row.items()
                if key is not None
            }
            spot_id = row["spot_option_id"]
            if (
                not spot_id
                or spot_id in seen_spot_ids
                or identity_areas.get(spot_id) != row["pilot_area_code"]
                or row["data_status"] != "PROTOTYPE"
                or row["input_method"] != "PM_MANUAL"
            ):
                raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")
            seen_spot_ids.add(spot_id)

            current = _population_range(
                row,
                "current_population_min",
                "current_population_max",
            )
            forecast_60 = _population_range(
                row,
                "forecast_60_population_min",
                "forecast_60_population_max",
            )
            forecast_180 = _population_range(
                row,
                "forecast_180_population_min",
                "forecast_180_population_max",
            )
            observed_at = _safe_time(row["observed_at"])
            updated_at = _safe_time(row["updated_at"])
            _safe_source_note(row["source_note"])
            if current is None and forecast_60 is None and forecast_180 is None:
                continue
            amount_60, rate_60 = _change(current, forecast_60)
            amount_180, rate_180 = _change(current, forecast_180)
            values[spot_id] = {
                "prototype_data_status": "PROTOTYPE",
                "spot_population_source": "PM_MANUAL_PROTOTYPE",
                "observed_at": observed_at,
                "current_population": current,
                "forecast_60": forecast_60,
                "forecast_180": forecast_180,
                "change_amount_60": amount_60,
                "change_rate_60": rate_60,
                "change_amount_180": amount_180,
                "change_rate_180": rate_180,
                "data_status": "PROTOTYPE",
                "input_method": "PM_MANUAL",
                "updated_at": updated_at,
            }
        json.dumps(values, allow_nan=False)
        return values

    @staticmethod
    def _unavailable() -> dict[str, object]:
        return {
            "prototype_data_status": SPOT_PROTOTYPE_DATA_UNAVAILABLE,
            "spot_population_source": None,
            "observed_at": None,
            "current_population": None,
            "forecast_60": None,
            "forecast_180": None,
            "change_amount_60": None,
            "change_rate_60": None,
            "change_amount_180": None,
            "change_rate_180": None,
            "data_status": None,
            "input_method": None,
            "updated_at": None,
        }

    def list_for_area(
        self,
        area_code: str,
    ) -> tuple[list[dict[str, object]], list[str]]:
        try:
            identities = load_pilot_spot_options(self._master_path)
        except PilotSpotOptionsError as exc:
            if str(exc) in {"reference_file_invalid", "reference_file_unreadable"}:
                raise SelectedAreaPilotError(
                    "AREA_DATA_PROVIDER_UNAVAILABLE"
                ) from exc
            raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID") from exc
        selected = [
            identity for identity in identities if identity["pilot_area_code"] == area_code
        ]
        if len(selected) != 3:
            raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")

        warnings: list[str] = []
        try:
            populations = self._population_rows(identities)
        except SelectedAreaPilotError:
            populations = {}
            warnings.append("SPOT_PROTOTYPE_CONTRACT_INVALID")

        spots: list[dict[str, object]] = []
        for identity in selected:
            spot = {
                "spot_option_id": identity["spot_option_id"],
                "spot_name": identity["spot_name"],
                "spot_type": identity["spot_type"],
                "address": identity["address"],
                "latitude": float(identity["latitude"]),
                "longitude": float(identity["longitude"]),
                "display_order": int(identity["display_order"]),
                "field_verification_status": identity["field_verification_status"],
                "operational_suitability_status": identity[
                    "operational_suitability_status"
                ],
                "limitations": list(_LIMITATIONS),
            }
            spot.update(populations.get(identity["spot_option_id"], self._unavailable()))
            spots.append(spot)
        if any(
            spot["prototype_data_status"] == SPOT_PROTOTYPE_DATA_UNAVAILABLE
            for spot in spots
        ):
            warnings.append(SPOT_PROTOTYPE_DATA_UNAVAILABLE)
        json.dumps(spots, allow_nan=False)
        return spots, warnings


class SelectedAreaPilotService:
    """Build the user-selected Area view without recommendation or persistence."""

    def __init__(
        self,
        *,
        area_provider: AreaDataProvider | None = None,
        spot_repository: PilotSpotOptionRepository | None = None,
    ) -> None:
        self._area_provider = area_provider or AreaDataProvider()
        self._spot_repository = spot_repository or PilotSpotOptionRepository()

    def list_areas(self) -> list[dict[str, object]]:
        return [
            {
                "area_code": area_code,
                "area_name": area_name,
                "display_order": display_order,
                "selection_mode": "USER_CHOICE",
            }
            for display_order, (area_code, area_name) in enumerate(
                PILOT_AREA_NAMES.items(),
                start=1,
            )
        ]

    def get_pilot_view(self, area_code: str) -> dict[str, object]:
        if area_code not in PILOT_AREA_NAMES:
            raise SelectedAreaPilotError("AREA_NOT_SUPPORTED")
        area = self._area_provider.get(area_code)
        spots, spot_warnings = self._spot_repository.list_for_area(area_code)
        warnings = ["DATA_UNAVAILABLE"]
        warnings.extend(spot_warnings)
        view = {
            "view_status": area["availability"],
            "area_selection_mode": "USER_CHOICE",
            "area_auto_recommendation": False,
            "spot_selection_mode": "USER_CHOICE",
            "spot_auto_recommendation": False,
            "machine_learning_used_for_recommendation": False,
            "official_recommendation_allowed": False,
            "area": area,
            "spot_options": spots,
            "warnings": warnings,
        }
        json.dumps(view, allow_nan=False)
        return view
