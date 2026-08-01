from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.main import app
from apps.api.schemas import AreaPilotResponse
from freshmanager.selected_area_pilot import SelectedAreaPilotError


class AreaPilotApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_areas_returns_five_approved_user_choice_areas(self) -> None:
        response = self.client.get("/api/v1/areas")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selection_mode"], "USER_CHOICE")
        self.assertEqual(
            [area["area_code"] for area in payload["areas"]],
            ["POI032", "POI088", "POI014", "POI025", "POI072"],
        )

    def test_pilot_view_returns_static_spots_with_unavailable_values(self) -> None:
        response = self.client.get("/api/v1/areas/POI032/pilot-view")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["view_status"], "DATA_UNAVAILABLE")
        self.assertEqual(payload["area"]["availability"], "DATA_UNAVAILABLE")
        self.assertIsNone(payload["area"]["current_population"])
        self.assertIsNone(payload["area"]["forecast_60"])
        self.assertIsNone(payload["area"]["forecast_180"])
        self.assertIn("DATA_UNAVAILABLE", payload["warnings"])
        self.assertIn("SPOT_PROTOTYPE_DATA_UNAVAILABLE", payload["warnings"])
        self.assertTrue(
            all(spot["spot_population_source"] is None for spot in payload["spot_options"])
        )
        self.assertTrue(all("source_note" not in spot for spot in payload["spot_options"]))
        self.assertEqual(len(payload["spot_options"]), 3)
        for spot in payload["spot_options"]:
            self.assertEqual(
                spot["prototype_data_status"],
                "SPOT_PROTOTYPE_DATA_UNAVAILABLE",
            )
            self.assertIsNone(spot["current_population"])
            self.assertIsNone(spot["forecast_60"])
            self.assertIsNone(spot["forecast_180"])
        serialized = json.dumps(payload, allow_nan=False)
        for forbidden in (
            "opportunity_score",
            "sales_score",
            "area_rank",
            "rank_percentile",
            "comparison_basis",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_public_status_fields_are_closed_in_openapi_and_validation(self) -> None:
        response = self.client.get("/api/v1/areas/POI032/pilot-view")
        payload = response.json()
        schemas = self.client.get("/openapi.json").json()["components"]["schemas"]

        def allowed_values(schema: dict[str, object]) -> set[object]:
            values = set(schema.get("enum", []))
            if "const" in schema:
                values.add(schema["const"])
            for option in schema.get("anyOf", []):
                if isinstance(option, dict):
                    values.update(allowed_values(option))
            return values

        expected = {
            ("AreaPilotResponse", "view_status"): {"DATA_UNAVAILABLE"},
            ("AreaPilotData", "availability"): {"DATA_UNAVAILABLE"},
            ("AreaPilotData", "freshness"): {"NO_COMPLETE_SNAPSHOT"},
            ("SpotOption", "field_verification_status"): {"UNAVAILABLE"},
            ("SpotOption", "operational_suitability_status"): {"NOT_VERIFIED"},
            ("SpotOption", "prototype_data_status"): {
                "PROTOTYPE",
                "SPOT_PROTOTYPE_DATA_UNAVAILABLE",
            },
            ("SpotOption", "spot_population_source"): {"PM_MANUAL_PROTOTYPE"},
            ("SpotOption", "data_status"): {"PROTOTYPE"},
            ("SpotOption", "input_method"): {"PM_MANUAL"},
        }
        for (model, field), values in expected.items():
            with self.subTest(model=model, field=field):
                self.assertEqual(
                    allowed_values(schemas[model]["properties"][field]),
                    values,
                )

        with self.assertRaises(ValidationError):
            AreaPilotResponse.model_validate({**payload, "view_status": "BROKEN"})

    def test_api_contract_has_no_user_geolocation(self) -> None:
        api_contract = json.dumps(
            self.client.get("/openapi.json").json(),
            ensure_ascii=False,
        ).lower()

        for forbidden in ("user_location", "user_latitude", "user_longitude"):
            self.assertNotIn(forbidden, api_contract)

    def test_unsupported_area_returns_bounded_404(self) -> None:
        response = self.client.get("/api/v1/areas/POI999/pilot-view")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "AREA_NOT_SUPPORTED",
                    "message": "지원하지 않는 Area입니다.",
                }
            },
        )

    def test_malformed_area_code_returns_bounded_422(self) -> None:
        response = self.client.get("/api/v1/areas/not-an-area/pilot-view")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_VALIDATION_FAILED")

    def test_static_spot_contract_error_returns_bounded_500(self) -> None:
        original = getattr(app.state, "pilot_service", None)

        class BrokenService:
            def get_pilot_view(self, _area_code: str) -> dict[str, object]:
                raise SelectedAreaPilotError("SPOT_PROTOTYPE_CONTRACT_INVALID")

        app.state.pilot_service = BrokenService()
        try:
            response = self.client.get("/api/v1/areas/POI032/pilot-view")
        finally:
            if original is None:
                del app.state.pilot_service
            else:
                app.state.pilot_service = original

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["error"]["code"],
            "SPOT_PROTOTYPE_CONTRACT_INVALID",
        )
        self.assertNotIn("traceback", response.text.lower())

    def test_provider_error_returns_bounded_503(self) -> None:
        original = getattr(app.state, "pilot_service", None)

        class BrokenService:
            def get_pilot_view(self, _area_code: str) -> dict[str, object]:
                raise SelectedAreaPilotError("AREA_DATA_PROVIDER_UNAVAILABLE")

        app.state.pilot_service = BrokenService()
        try:
            response = self.client.get("/api/v1/areas/POI032/pilot-view")
        finally:
            if original is None:
                del app.state.pilot_service
            else:
                app.state.pilot_service = original

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "AREA_DATA_PROVIDER_UNAVAILABLE",
        )

    def test_unclassified_domain_error_returns_bounded_500(self) -> None:
        original = getattr(app.state, "pilot_service", None)

        class BrokenService:
            def get_pilot_view(self, _area_code: str) -> dict[str, object]:
                raise SelectedAreaPilotError("unexpected_domain_failure")

        app.state.pilot_service = BrokenService()
        try:
            response = self.client.get("/api/v1/areas/POI032/pilot-view")
        finally:
            if original is None:
                del app.state.pilot_service
            else:
                app.state.pilot_service = original

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_SERVER_ERROR")
        self.assertNotIn("unexpected_domain_failure", response.text)


if __name__ == "__main__":
    unittest.main()
