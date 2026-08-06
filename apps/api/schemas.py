from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["freshmanager-api"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AreaListItem(BaseModel):
    area_code: str
    area_name: str
    display_order: int
    selection_mode: Literal["USER_CHOICE"]


class AreasResponse(BaseModel):
    areas: list[AreaListItem]
    selection_mode: Literal["USER_CHOICE"]


class PopulationRange(BaseModel):
    min: float
    max: float


class AreaPilotData(BaseModel):
    area_code: str
    area_name: str
    source: str | None
    availability: Literal["DATA_UNAVAILABLE"]
    freshness: Literal["NO_COMPLETE_SNAPSHOT"]
    observed_at: str | None
    current_population: PopulationRange | None
    forecast_60: PopulationRange | None
    forecast_180: PopulationRange | None
    congestion_level: str | None
    forecast_60_congestion_level: str | None
    forecast_180_congestion_level: str | None
    forecast_60_target_at: str | None
    forecast_180_target_at: str | None
    change_amount_60: float | None
    change_rate_60: float | None
    change_amount_180: float | None
    change_rate_180: float | None


class SpotOption(BaseModel):
    spot_option_id: str
    spot_name: str
    spot_type: str
    address: str
    latitude: float
    longitude: float
    display_order: int
    field_verification_status: Literal["UNAVAILABLE"]
    operational_suitability_status: Literal["NOT_VERIFIED"]
    limitations: list[str]
    prototype_data_status: Literal["PROTOTYPE", "SPOT_PROTOTYPE_DATA_UNAVAILABLE"]
    spot_population_source: Literal["PM_MANUAL_PROTOTYPE"] | None
    observed_at: str | None
    current_population: PopulationRange | None
    forecast_60: PopulationRange | None
    forecast_180: PopulationRange | None
    change_amount_60: float | None
    change_rate_60: float | None
    change_amount_180: float | None
    change_rate_180: float | None
    data_status: Literal["PROTOTYPE"] | None
    input_method: Literal["PM_MANUAL"] | None
    updated_at: str | None


class AreaPilotResponse(BaseModel):
    view_status: Literal["DATA_UNAVAILABLE"]
    area_selection_mode: Literal["USER_CHOICE"]
    area_auto_recommendation: Literal[False]
    spot_selection_mode: Literal["USER_CHOICE"]
    spot_auto_recommendation: Literal[False]
    machine_learning_used_for_recommendation: Literal[False]
    official_recommendation_allowed: Literal[False]
    area: AreaPilotData
    spot_options: list[SpotOption]
    warnings: list[str]
