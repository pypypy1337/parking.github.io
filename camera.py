from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any


def render_camera_snapshot_svg(state: dict[str, Any], camera_id: str, width: int = 960, height: int = 540) -> str:
    camera = _find_camera(state, camera_id)
    zones = _zones_for_camera(state, camera_id)
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    camera_name = html.escape(camera["name"])
    source = html.escape(camera.get("rtsp_url", ""))

    zone_markup = []
    for zone in zones:
        x = zone["x"] * width / 100
        y = zone["y"] * height / 100
        zone_width = zone["width"] * width / 100
        zone_height = zone["height"] * height / 100
        label = _zone_label(zone)
        class_name = _zone_class(zone)
        zone_markup.append(
            f"""
            <g>
              <rect x="{x:.2f}" y="{y:.2f}" width="{zone_width:.2f}" height="{zone_height:.2f}" rx="8" class="{class_name}" />
              <text x="{x + 12:.2f}" y="{y + 28:.2f}" class="zone-label">{html.escape(label)}</text>
            </g>
            """
        )
        if zone.get("vehicle_present"):
            zone_markup.append(
                f"""
                <ellipse cx="{x + zone_width / 2:.2f}" cy="{y + zone_height / 2:.2f}"
                    rx="{max(zone_width * 0.28, 18):.2f}" ry="{max(zone_height * 0.22, 12):.2f}" class="vehicle" />
                """
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <style>
    .surface {{ fill: #283033; }}
    .lane {{ stroke: #f1f5f9; stroke-width: 3; stroke-dasharray: 18 16; opacity: .42; }}
    .grid {{ stroke: #475569; stroke-width: 1; opacity: .35; }}
    .parking-free {{ fill: rgba(22, 163, 74, .20); stroke: #16a34a; stroke-width: 4; }}
    .parking-detecting {{ fill: rgba(234, 179, 8, .25); stroke: #eab308; stroke-width: 4; }}
    .parking-occupied {{ fill: rgba(220, 38, 38, .28); stroke: #dc2626; stroke-width: 4; }}
    .forbidden {{ fill: rgba(249, 115, 22, .22); stroke: #f97316; stroke-width: 4; }}
    .zone-label {{ fill: #f8fafc; font: 700 22px system-ui, sans-serif; paint-order: stroke; stroke: #0f172a; stroke-width: 4; }}
    .vehicle {{ fill: #0f172a; stroke: #e2e8f0; stroke-width: 4; opacity: .94; }}
    .title {{ fill: #f8fafc; font: 700 28px system-ui, sans-serif; }}
    .subtitle {{ fill: #cbd5e1; font: 18px system-ui, sans-serif; }}
  </style>
  <rect width="{width}" height="{height}" class="surface" />
  <path d="M 0 {height * .48:.0f} L {width} {height * .48:.0f}" class="lane" />
  <path d="M 0 {height * .70:.0f} L {width} {height * .70:.0f}" class="lane" />
  <path d="M {width * .20:.0f} 0 L {width * .20:.0f} {height}" class="grid" />
  <path d="M {width * .40:.0f} 0 L {width * .40:.0f} {height}" class="grid" />
  <path d="M {width * .60:.0f} 0 L {width * .60:.0f} {height}" class="grid" />
  <path d="M {width * .80:.0f} 0 L {width * .80:.0f} {height}" class="grid" />
  {''.join(zone_markup)}
  <rect x="24" y="24" width="{width - 48}" height="74" rx="10" fill="#0f172a" opacity=".72" />
  <text x="48" y="58" class="title">{camera_name}</text>
  <text x="48" y="84" class="subtitle">{source} · {now}</text>
</svg>"""


def _find_camera(state: dict[str, Any], camera_id: str) -> dict[str, Any]:
    for camera in state.get("cameras", []):
        if camera.get("id") == camera_id:
            return camera
    raise KeyError(f"camera not found: {camera_id}")


def _zones_for_camera(state: dict[str, Any], camera_id: str) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for space in state.get("spaces", []):
        camera_observes_space = camera_id in space.get("camera_ids", [])
        for zone in space.get("zones", []):
            if zone.get("camera_id") == camera_id or (zone.get("camera_id") is None and camera_observes_space):
                zones.append(zone)
    return zones


def _zone_label(zone: dict[str, Any]) -> str:
    if zone.get("kind") == "forbidden":
        return f"X{zone.get('number', '')}"
    if zone.get("occupied_number"):
        return f"P{zone.get('number', '')} / #{zone['occupied_number']}"
    return f"P{zone.get('number', '')}"


def _zone_class(zone: dict[str, Any]) -> str:
    if zone.get("kind") == "forbidden":
        return "forbidden"
    if zone.get("occupied"):
        return "parking-occupied"
    if zone.get("vehicle_present"):
        return "parking-detecting"
    return "parking-free"


class Camera:
    """Compatibility class for the original console demo."""

    def __init__(self, name: str, x1: int, y1: int, x2: int, y2: int):
        self.name = name
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2

    def monitor_parking(self, parking: Any) -> None:
        print(f"Камера '{self.name}': {parking.check_occupancy()}")

    def get_coordinates(self) -> str:
        return f"'{self.name}' следит за областью: ({self.x1}, {self.y1}, {self.x2}, {self.y2})"
