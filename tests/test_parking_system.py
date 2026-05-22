import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from parking import ParkingSystem


def find_zone(state, zone_id):
    for space in state["spaces"]:
        for zone in space["zones"]:
            if zone["id"] == zone_id:
                return zone
    raise AssertionError(f"zone {zone_id} not found")


class ParkingSystemTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.data_path = Path(self.tmpdir.name) / "parking_state.json"

    def test_cameras_spaces_and_zones_are_persisted(self):
        system = ParkingSystem(self.data_path)

        camera = system.add_camera("Северный въезд", "rtsp://camera.local/stream")
        space = system.add_space("Парковка A", camera_ids=[camera["id"]])
        parking_zone = system.add_zone(
            space["id"],
            kind="parking",
            camera_id=camera["id"],
            x=10,
            y=20,
            width=30,
            height=18,
        )
        forbidden_zone = system.add_zone(
            space["id"],
            kind="forbidden",
            camera_id=camera["id"],
            x=60,
            y=12,
            width=20,
            height=20,
        )

        reloaded = ParkingSystem(self.data_path)
        state = reloaded.get_state()

        self.assertEqual(state["cameras"][0]["name"], "Северный въезд")
        self.assertEqual(state["spaces"][0]["name"], "Парковка A")
        self.assertEqual(state["spaces"][0]["camera_ids"], [camera["id"]])
        self.assertEqual(parking_zone["number"], 1)
        self.assertEqual(forbidden_zone["number"], 1)
        self.assertEqual(len(state["spaces"][0]["zones"]), 2)

    def test_occupancy_waits_for_configured_interval_and_renumbers(self):
        system = ParkingSystem(self.data_path)
        system.update_settings(occupancy_interval_seconds=300)
        camera = system.add_camera("Камера", "mock://camera")
        space = system.add_space("Парковка", camera_ids=[camera["id"]])
        first = system.add_zone(space["id"], kind="parking", camera_id=camera["id"], x=0, y=0, width=20, height=20)
        second = system.add_zone(space["id"], kind="parking", camera_id=camera["id"], x=25, y=0, width=20, height=20)
        started_at = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)

        system.set_vehicle_presence(first["id"], True, timestamp=started_at)
        state = system.refresh_occupancy(timestamp=started_at + timedelta(seconds=299))
        self.assertFalse(find_zone(state, first["id"])["occupied"])

        system.set_vehicle_presence(second["id"], True, timestamp=started_at)
        state = system.refresh_occupancy(timestamp=started_at + timedelta(seconds=300))
        self.assertTrue(find_zone(state, first["id"])["occupied"])
        self.assertTrue(find_zone(state, second["id"])["occupied"])
        self.assertEqual(find_zone(state, first["id"])["occupied_number"], 1)
        self.assertEqual(find_zone(state, second["id"])["occupied_number"], 2)

        system.set_vehicle_presence(first["id"], False, timestamp=started_at + timedelta(seconds=301))
        state = system.refresh_occupancy(timestamp=started_at + timedelta(seconds=301))
        self.assertFalse(find_zone(state, first["id"])["occupied"])
        self.assertEqual(find_zone(state, second["id"])["occupied_number"], 1)


class FlaskApiTests(unittest.TestCase):
    def setUp(self):
        try:
            from main import create_app
        except ModuleNotFoundError as exc:
            if exc.name == "flask":
                self.skipTest("Flask is not installed")
            raise

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.data_path = Path(self.tmpdir.name) / "parking_state.json"
        try:
            self.app = create_app(data_path=self.data_path)
        except ModuleNotFoundError as exc:
            if exc.name == "flask":
                self.skipTest("Flask is not installed")
            raise
        self.client = self.app.test_client()

    def test_api_creates_camera_space_and_zone(self):
        camera_response = self.client.post(
            "/api/cameras",
            json={"name": "Камера API", "rtsp_url": "mock://api"},
        )
        self.assertEqual(camera_response.status_code, 201)
        camera = camera_response.get_json()["camera"]

        space_response = self.client.post(
            "/api/spaces",
            json={"name": "API парковка", "camera_ids": [camera["id"]]},
        )
        self.assertEqual(space_response.status_code, 201)
        space = space_response.get_json()["space"]

        zone_response = self.client.post(
            f"/api/spaces/{space['id']}/zones",
            json={
                "kind": "parking",
                "camera_id": camera["id"],
                "x": 5,
                "y": 5,
                "width": 25,
                "height": 25,
            },
        )
        self.assertEqual(zone_response.status_code, 201)

        state_response = self.client.get("/api/state")
        self.assertEqual(state_response.status_code, 200)
        state = state_response.get_json()
        self.assertEqual(state["summary"]["total_parking_zones"], 1)
        self.assertEqual(state["summary"]["free_zones"], 1)


if __name__ == "__main__":
    unittest.main()
