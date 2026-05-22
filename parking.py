from __future__ import annotations

import copy
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_DATA_PATH = Path(os.environ.get("PARKING_DATA_PATH", "data/parking_state.json"))
VALID_ZONE_KINDS = {"parking", "forbidden"}


class ParkingSystemError(ValueError):
    """Raised when an API request cannot be applied to parking state."""


class ParkingSystemNotFound(KeyError):
    """Raised when an entity id does not exist in parking state."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_timestamp(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    normalized = str(value).strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def default_state() -> dict[str, Any]:
    now = format_timestamp(utc_now())
    return {
        "version": 1,
        "settings": {
            "occupancy_interval_seconds": 300,
            "yolo_model": "yolov12.pt",
            "debug": False,
        },
        "cameras": [],
        "spaces": [],
        "events": [],
        "created_at": now,
        "updated_at": now,
    }


class JsonStateStore:
    def __init__(self, path: str | Path = DEFAULT_DATA_PATH):
        self.path = Path(path)
        self._lock = RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return self._normalize(default_state())

            with self.path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
            return self._normalize(state)

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            normalized = self._normalize(state)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._backup_current_file()

            temporary_path = self.path.with_name(f".{self.path.name}.tmp")
            with temporary_path.open("w", encoding="utf-8") as handle:
                json.dump(normalized, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary_path, self.path)
            return copy.deepcopy(normalized)

    def _backup_current_file(self) -> None:
        if not self.path.exists():
            return

        backup_dir = self.path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_path = backup_dir / f"{self.path.stem}-{stamp}.json"
        shutil.copy2(self.path, backup_path)

        backups = sorted(backup_dir.glob(f"{self.path.stem}-*.json"))
        for old_backup in backups[:-20]:
            old_backup.unlink(missing_ok=True)

    def _normalize(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized = default_state()
        normalized.update(state or {})
        normalized["settings"] = {**default_state()["settings"], **normalized.get("settings", {})}
        normalized["cameras"] = list(normalized.get("cameras") or [])
        normalized["spaces"] = list(normalized.get("spaces") or [])
        normalized["events"] = list(normalized.get("events") or [])

        for camera in normalized["cameras"]:
            camera.setdefault("space_ids", [])
            camera.setdefault("enabled", True)
            camera.setdefault("created_at", normalized["created_at"])
            camera.setdefault("updated_at", normalized["updated_at"])

        for space in normalized["spaces"]:
            space.setdefault("camera_ids", [])
            space.setdefault("zones", [])
            space.setdefault("created_at", normalized["created_at"])
            space.setdefault("updated_at", normalized["updated_at"])
            for zone in space["zones"]:
                zone.setdefault("kind", "parking")
                zone.setdefault("number", 1)
                zone.setdefault("camera_id", None)
                zone.setdefault("x", 0.0)
                zone.setdefault("y", 0.0)
                zone.setdefault("width", 20.0)
                zone.setdefault("height", 12.0)
                zone.setdefault("vehicle_present", False)
                zone.setdefault("detected_since", None)
                zone.setdefault("occupied", False)
                zone.setdefault("occupied_since", None)
                zone.setdefault("occupied_number", None)
                zone.setdefault("created_at", normalized["created_at"])
                zone.setdefault("updated_at", normalized["updated_at"])

        return normalized


class ParkingSystem:
    def __init__(self, data_path: str | Path = DEFAULT_DATA_PATH):
        self.store = JsonStateStore(data_path or DEFAULT_DATA_PATH)
        self._lock = RLock()
        if not self.store.path.exists():
            self.store.save(self.store.load())

    def get_state(self) -> dict[str, Any]:
        return self.refresh_occupancy()

    def add_camera(self, name: str, rtsp_url: str, enabled: bool = True) -> dict[str, Any]:
        self._require_text(name, "name")
        self._require_text(rtsp_url, "rtsp_url")
        timestamp = format_timestamp(utc_now())
        camera = {
            "id": new_id("cam"),
            "name": name.strip(),
            "rtsp_url": rtsp_url.strip(),
            "space_ids": [],
            "enabled": bool(enabled),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        with self._lock:
            state = self.store.load()
            state["cameras"].append(camera)
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(camera)

    def update_camera(self, camera_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            state = self.store.load()
            camera = self._find_camera(state, camera_id)
            if "name" in updates:
                self._require_text(updates["name"], "name")
                camera["name"] = updates["name"].strip()
            if "rtsp_url" in updates:
                self._require_text(updates["rtsp_url"], "rtsp_url")
                camera["rtsp_url"] = updates["rtsp_url"].strip()
            if "enabled" in updates:
                camera["enabled"] = bool(updates["enabled"])
            camera["updated_at"] = format_timestamp(utc_now())
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(camera)

    def delete_camera(self, camera_id: str) -> None:
        with self._lock:
            state = self.store.load()
            self._find_camera(state, camera_id)
            state["cameras"] = [camera for camera in state["cameras"] if camera["id"] != camera_id]
            for space in state["spaces"]:
                space["camera_ids"] = [item for item in space.get("camera_ids", []) if item != camera_id]
                for zone in space.get("zones", []):
                    if zone.get("camera_id") == camera_id:
                        zone["camera_id"] = None
            self._touch(state)
            self.store.save(state)

    def add_space(self, name: str, camera_ids: list[str] | None = None) -> dict[str, Any]:
        self._require_text(name, "name")
        timestamp = format_timestamp(utc_now())
        camera_ids = self._dedupe(camera_ids or [])
        with self._lock:
            state = self.store.load()
            self._assert_cameras_exist(state, camera_ids)
            space = {
                "id": new_id("space"),
                "name": name.strip(),
                "camera_ids": camera_ids,
                "zones": [],
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            state["spaces"].append(space)
            self._sync_camera_assignments(state)
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(space)

    def update_space(self, space_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            state = self.store.load()
            space = self._find_space(state, space_id)
            if "name" in updates:
                self._require_text(updates["name"], "name")
                space["name"] = updates["name"].strip()
            if "camera_ids" in updates:
                camera_ids = self._dedupe(updates["camera_ids"] or [])
                self._assert_cameras_exist(state, camera_ids)
                space["camera_ids"] = camera_ids
                self._sync_camera_assignments(state)
            space["updated_at"] = format_timestamp(utc_now())
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(space)

    def delete_space(self, space_id: str) -> None:
        with self._lock:
            state = self.store.load()
            self._find_space(state, space_id)
            state["spaces"] = [space for space in state["spaces"] if space["id"] != space_id]
            self._sync_camera_assignments(state)
            self._touch(state)
            self.store.save(state)

    def add_zone(
        self,
        space_id: str,
        *,
        kind: str,
        camera_id: str | None = None,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        kind = self._validate_kind(kind)
        rect = self._normalize_rect(x, y, width, height)
        timestamp = format_timestamp(utc_now())
        with self._lock:
            state = self.store.load()
            space = self._find_space(state, space_id)
            if camera_id:
                self._find_camera(state, camera_id)
                if camera_id not in space["camera_ids"]:
                    space["camera_ids"].append(camera_id)
                    self._sync_camera_assignments(state)

            zone = {
                "id": new_id("zone"),
                "kind": kind,
                "number": self._next_zone_number(space, kind),
                "camera_id": camera_id,
                **rect,
                "vehicle_present": False,
                "detected_since": None,
                "occupied": False,
                "occupied_since": None,
                "occupied_number": None,
                "created_at": timestamp,
                "updated_at": timestamp,
            }
            space["zones"].append(zone)
            space["updated_at"] = timestamp
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(zone)

    def update_zone(self, zone_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            state = self.store.load()
            space, zone = self._find_zone(state, zone_id)
            if "kind" in updates:
                zone["kind"] = self._validate_kind(updates["kind"])
                if zone["kind"] == "forbidden":
                    zone["vehicle_present"] = False
                    zone["detected_since"] = None
                    zone["occupied"] = False
                    zone["occupied_since"] = None
                    zone["occupied_number"] = None
            if "camera_id" in updates:
                camera_id = updates["camera_id"] or None
                if camera_id:
                    self._find_camera(state, camera_id)
                    if camera_id not in space["camera_ids"]:
                        space["camera_ids"].append(camera_id)
                        self._sync_camera_assignments(state)
                zone["camera_id"] = camera_id
            if any(key in updates for key in ("x", "y", "width", "height")):
                current = {key: zone[key] for key in ("x", "y", "width", "height")}
                current.update({key: updates[key] for key in current if key in updates})
                zone.update(self._normalize_rect(**current))
            if "vehicle_present" in updates:
                self._apply_vehicle_presence(zone, bool(updates["vehicle_present"]), utc_now())
            timestamp = format_timestamp(utc_now())
            zone["updated_at"] = timestamp
            space["updated_at"] = timestamp
            self._renumber_zones(space)
            self._touch(state)
            self._apply_occupancy(state, utc_now())
            self.store.save(state)
        return copy.deepcopy(zone)

    def delete_zone(self, zone_id: str) -> None:
        with self._lock:
            state = self.store.load()
            space, _ = self._find_zone(state, zone_id)
            space["zones"] = [zone for zone in space["zones"] if zone["id"] != zone_id]
            self._renumber_zones(space)
            space["updated_at"] = format_timestamp(utc_now())
            self._touch(state)
            self.store.save(state)

    def set_vehicle_presence(
        self,
        zone_id: str,
        present: bool,
        timestamp: str | datetime | None = None,
    ) -> dict[str, Any]:
        when = parse_timestamp(timestamp) or utc_now()
        with self._lock:
            state = self.store.load()
            _, zone = self._find_zone(state, zone_id)
            if zone["kind"] != "parking":
                raise ParkingSystemError("vehicle presence can only be applied to parking zones")
            self._apply_vehicle_presence(zone, bool(present), when)
            self._apply_occupancy(state, when)
            self._record_event(state, zone_id, "vehicle_present" if present else "vehicle_absent", when)
            self._touch(state, when)
            self.store.save(state)
        return copy.deepcopy(zone)

    def update_settings(self, **settings: Any) -> dict[str, Any]:
        with self._lock:
            state = self.store.load()
            if "occupancy_interval_seconds" in settings:
                interval = int(settings["occupancy_interval_seconds"])
                if interval <= 0:
                    raise ParkingSystemError("occupancy_interval_seconds must be greater than zero")
                state["settings"]["occupancy_interval_seconds"] = interval
            if "yolo_model" in settings:
                self._require_text(settings["yolo_model"], "yolo_model")
                state["settings"]["yolo_model"] = settings["yolo_model"].strip()
            if "debug" in settings:
                state["settings"]["debug"] = bool(settings["debug"])
            self._touch(state)
            self.store.save(state)
        return copy.deepcopy(state["settings"])

    def refresh_occupancy(self, timestamp: str | datetime | None = None) -> dict[str, Any]:
        when = parse_timestamp(timestamp) or utc_now()
        with self._lock:
            state = self.store.load()
            changed = self._apply_occupancy(state, when)
            if changed:
                self._touch(state, when)
                self.store.save(state)
            return self._with_summary(state)

    def _apply_vehicle_presence(self, zone: dict[str, Any], present: bool, when: datetime) -> None:
        zone["vehicle_present"] = present
        zone["updated_at"] = format_timestamp(when)
        if present and not zone.get("detected_since"):
            zone["detected_since"] = format_timestamp(when)
        if not present:
            zone["detected_since"] = None
            zone["occupied"] = False
            zone["occupied_since"] = None
            zone["occupied_number"] = None

    def _apply_occupancy(self, state: dict[str, Any], when: datetime) -> bool:
        changed = False
        interval = int(state["settings"].get("occupancy_interval_seconds", 300))
        for space in state["spaces"]:
            for zone in space.get("zones", []):
                if zone.get("kind") != "parking":
                    continue

                was_occupied = bool(zone.get("occupied"))
                should_be_occupied = False
                if zone.get("vehicle_present") and zone.get("detected_since"):
                    detected_since = parse_timestamp(zone["detected_since"])
                    should_be_occupied = bool(detected_since and (when - detected_since).total_seconds() >= interval)

                if should_be_occupied != was_occupied:
                    changed = True
                    zone["occupied"] = should_be_occupied
                    zone["occupied_since"] = format_timestamp(when) if should_be_occupied else None
                    zone["updated_at"] = format_timestamp(when)

            changed = self._renumber_occupied_zones(space) or changed
        return changed

    def _with_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        snapshot = copy.deepcopy(state)
        total_parking = 0
        occupied = 0
        forbidden = 0
        spaces_summary = []

        for space in snapshot["spaces"]:
            parking_zones = [zone for zone in space["zones"] if zone["kind"] == "parking"]
            forbidden_zones = [zone for zone in space["zones"] if zone["kind"] == "forbidden"]
            occupied_zones = [zone for zone in parking_zones if zone.get("occupied")]
            free_zones = len(parking_zones) - len(occupied_zones)
            total_parking += len(parking_zones)
            occupied += len(occupied_zones)
            forbidden += len(forbidden_zones)
            spaces_summary.append(
                {
                    "space_id": space["id"],
                    "name": space["name"],
                    "parking_zones": len(parking_zones),
                    "occupied_zones": len(occupied_zones),
                    "free_zones": free_zones,
                    "forbidden_zones": len(forbidden_zones),
                }
            )

        snapshot["summary"] = {
            "cameras": len(snapshot["cameras"]),
            "space_count": len(snapshot["spaces"]),
            "total_parking_zones": total_parking,
            "occupied_zones": occupied,
            "free_zones": total_parking - occupied,
            "forbidden_zones": forbidden,
            "spaces": spaces_summary,
        }
        return snapshot

    def _find_camera(self, state: dict[str, Any], camera_id: str) -> dict[str, Any]:
        for camera in state["cameras"]:
            if camera["id"] == camera_id:
                return camera
        raise ParkingSystemNotFound(f"camera not found: {camera_id}")

    def _find_space(self, state: dict[str, Any], space_id: str) -> dict[str, Any]:
        for space in state["spaces"]:
            if space["id"] == space_id:
                return space
        raise ParkingSystemNotFound(f"parking space not found: {space_id}")

    def _find_zone(self, state: dict[str, Any], zone_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for space in state["spaces"]:
            for zone in space.get("zones", []):
                if zone["id"] == zone_id:
                    return space, zone
        raise ParkingSystemNotFound(f"zone not found: {zone_id}")

    def _assert_cameras_exist(self, state: dict[str, Any], camera_ids: list[str]) -> None:
        for camera_id in camera_ids:
            self._find_camera(state, camera_id)

    def _sync_camera_assignments(self, state: dict[str, Any]) -> None:
        assignments: dict[str, list[str]] = {camera["id"]: [] for camera in state["cameras"]}
        for space in state["spaces"]:
            for camera_id in space.get("camera_ids", []):
                if camera_id in assignments and space["id"] not in assignments[camera_id]:
                    assignments[camera_id].append(space["id"])
        for camera in state["cameras"]:
            camera["space_ids"] = assignments.get(camera["id"], [])

    def _record_event(self, state: dict[str, Any], zone_id: str, event_type: str, when: datetime) -> None:
        state["events"].append(
            {
                "id": new_id("event"),
                "zone_id": zone_id,
                "type": event_type,
                "created_at": format_timestamp(when),
            }
        )
        state["events"] = state["events"][-200:]

    def _touch(self, state: dict[str, Any], when: datetime | None = None) -> None:
        state["updated_at"] = format_timestamp(when or utc_now())

    def _renumber_zones(self, space: dict[str, Any]) -> None:
        for kind in VALID_ZONE_KINDS:
            number = 1
            for zone in space.get("zones", []):
                if zone["kind"] == kind:
                    zone["number"] = number
                    number += 1

    def _renumber_occupied_zones(self, space: dict[str, Any]) -> bool:
        changed = False
        number = 1
        for zone in space.get("zones", []):
            expected_number = number if zone["kind"] == "parking" and zone.get("occupied") else None
            if zone.get("occupied_number") != expected_number:
                changed = True
                zone["occupied_number"] = expected_number
            if expected_number is not None:
                number += 1
        return changed

    def _next_zone_number(self, space: dict[str, Any], kind: str) -> int:
        existing = [zone.get("number", 0) for zone in space.get("zones", []) if zone.get("kind") == kind]
        return max(existing or [0]) + 1

    def _validate_kind(self, kind: str) -> str:
        if kind not in VALID_ZONE_KINDS:
            raise ParkingSystemError(f"zone kind must be one of: {', '.join(sorted(VALID_ZONE_KINDS))}")
        return kind

    def _normalize_rect(self, x: float, y: float, width: float, height: float) -> dict[str, float]:
        values = {
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
        }
        if values["width"] <= 0 or values["height"] <= 0:
            raise ParkingSystemError("zone width and height must be greater than zero")
        values["x"] = min(max(values["x"], 0.0), 99.0)
        values["y"] = min(max(values["y"], 0.0), 99.0)
        values["width"] = min(max(values["width"], 1.0), 100.0 - values["x"])
        values["height"] = min(max(values["height"], 1.0), 100.0 - values["y"])
        return values

    def _require_text(self, value: Any, field: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ParkingSystemError(f"{field} is required")

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped


class Parking:
    """Compatibility class for the original console demo."""

    def __init__(self, parking_stage: str):
        self.parking_stage = parking_stage
        self.is_occupied = False

    def check_occupancy(self) -> str:
        return f"Место '{self.parking_stage}' {'занято' if self.is_occupied else 'свободно'}"

    def occupy(self) -> None:
        self.is_occupied = True

    def free(self) -> None:
        self.is_occupied = False
