from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from camera import render_camera_snapshot_svg
from parking import DEFAULT_DATA_PATH, ParkingSystem, ParkingSystemError, ParkingSystemNotFound

try:
    from flask import Flask, Response, jsonify, render_template, request
except ModuleNotFoundError:  # pragma: no cover - allows core tests without Flask installed
    Flask = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]
    render_template = None  # type: ignore[assignment]
    request = None  # type: ignore[assignment]


def create_app(data_path: str | Path | None = None) -> Flask:
    if Flask is None:
        raise ModuleNotFoundError("No module named 'flask'", name="flask")

    app = Flask(__name__, template_folder=".", static_folder="static")
    system = ParkingSystem(data_path or os.environ.get("PARKING_DATA_PATH", DEFAULT_DATA_PATH))

    @app.errorhandler(ParkingSystemError)
    @app.errorhandler(ValueError)
    def handle_bad_request(error: Exception):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(ParkingSystemNotFound)
    @app.errorhandler(KeyError)
    def handle_not_found(error: Exception):
        return jsonify({"error": str(error).strip("'")}), 404

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/state")
    def get_state():
        return jsonify(system.get_state())

    @app.post("/api/cameras")
    def add_camera():
        payload = json_payload()
        camera = system.add_camera(
            payload.get("name", ""),
            payload.get("rtsp_url", ""),
            enabled=payload.get("enabled", True),
        )
        return jsonify({"camera": camera}), 201

    @app.patch("/api/cameras/<camera_id>")
    def update_camera(camera_id: str):
        camera = system.update_camera(camera_id, **json_payload())
        return jsonify({"camera": camera})

    @app.delete("/api/cameras/<camera_id>")
    def delete_camera(camera_id: str):
        system.delete_camera(camera_id)
        return "", 204

    @app.post("/api/spaces")
    def add_space():
        payload = json_payload()
        space = system.add_space(payload.get("name", ""), camera_ids=payload.get("camera_ids") or [])
        return jsonify({"space": space}), 201

    @app.patch("/api/spaces/<space_id>")
    def update_space(space_id: str):
        space = system.update_space(space_id, **json_payload())
        return jsonify({"space": space})

    @app.delete("/api/spaces/<space_id>")
    def delete_space(space_id: str):
        system.delete_space(space_id)
        return "", 204

    @app.post("/api/spaces/<space_id>/zones")
    def add_zone(space_id: str):
        payload = json_payload()
        zone = system.add_zone(
            space_id,
            kind=payload.get("kind", "parking"),
            camera_id=payload.get("camera_id"),
            x=payload.get("x", 5),
            y=payload.get("y", 5),
            width=payload.get("width", 20),
            height=payload.get("height", 14),
        )
        return jsonify({"zone": zone}), 201

    @app.patch("/api/zones/<zone_id>")
    def update_zone(zone_id: str):
        zone = system.update_zone(zone_id, **json_payload())
        return jsonify({"zone": zone})

    @app.delete("/api/zones/<zone_id>")
    def delete_zone(zone_id: str):
        system.delete_zone(zone_id)
        return "", 204

    @app.post("/api/zones/<zone_id>/vehicle")
    def set_vehicle_presence(zone_id: str):
        payload = json_payload()
        zone = system.set_vehicle_presence(zone_id, bool(payload.get("present")), payload.get("timestamp"))
        return jsonify({"zone": zone})

    @app.patch("/api/settings")
    @app.post("/api/settings")
    def update_settings():
        settings = system.update_settings(**json_payload())
        return jsonify({"settings": settings})

    @app.post("/api/refresh")
    def refresh():
        return jsonify(system.refresh_occupancy(json_payload().get("timestamp")))

    @app.get("/camera/<camera_id>/snapshot.svg")
    def camera_snapshot(camera_id: str):
        svg = render_camera_snapshot_svg(system.get_state(), camera_id)
        return Response(
            svg,
            status=200,
            mimetype="image/svg+xml",
            headers={"Cache-Control": "no-store"},
        )

    return app


def json_payload() -> dict[str, Any]:
    payload = request.get_json(silent=True) if request is not None else None
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
