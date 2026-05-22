const appState = {
    state: null,
    view: "work",
    selectedSpaceId: null,
    selectedCameraId: null,
    selectedZoneId: null,
    zoneKind: "parking",
    drag: null
};

const nodes = {
    statusLine: document.getElementById("statusLine"),
    systemStamp: document.getElementById("systemStamp"),
    metricsGrid: document.getElementById("metricsGrid"),
    cameraFeeds: document.getElementById("cameraFeeds"),
    spaceList: document.getElementById("spaceList"),
    spaceDetail: document.getElementById("spaceDetail"),
    spaceCameraChoices: document.getElementById("spaceCameraChoices"),
    spaceSelect: document.getElementById("spaceSelect"),
    cameraSelect: document.getElementById("cameraSelect"),
    editorViewport: document.getElementById("editorViewport"),
    editorFrame: document.getElementById("editorFrame"),
    editorZones: document.getElementById("editorZones"),
    zoneList: document.getElementById("zoneList"),
    zoneEditor: document.getElementById("zoneEditor"),
    zoneEditorFields: document.getElementById("zoneEditorFields"),
    vehicleToggle: document.getElementById("vehicleToggle"),
    deleteZone: document.getElementById("deleteZone")
};

function showStatus(message, error = false) {
    nodes.statusLine.textContent = message || "";
    nodes.statusLine.classList.toggle("error", error);
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options
    });
    if (response.status === 204) {
        return null;
    }
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload.error || `HTTP ${response.status}`);
    }
    return payload;
}

async function loadState(silent = false) {
    try {
        appState.state = await api("/api/state");
        ensureSelections();
        render();
        if (!silent) {
            showStatus("Состояние обновлено");
        }
    } catch (error) {
        showStatus(error.message, true);
    }
}

function ensureSelections() {
    const state = appState.state;
    if (!state) {
        return;
    }

    if (!state.spaces.some((space) => space.id === appState.selectedSpaceId)) {
        appState.selectedSpaceId = state.spaces[0]?.id || null;
    }

    const selectedSpace = getSelectedSpace();
    const preferredCamera = selectedSpace?.camera_ids?.[0];
    if (!state.cameras.some((camera) => camera.id === appState.selectedCameraId)) {
        appState.selectedCameraId = preferredCamera || state.cameras[0]?.id || null;
    }

    if (!getSelectedZone()) {
        appState.selectedZoneId = selectedSpace?.zones?.[0]?.id || null;
    }
}

function render() {
    if (!appState.state) {
        return;
    }
    nodes.systemStamp.textContent = `Обновлено: ${formatDate(appState.state.updated_at)}`;
    renderMetrics();
    renderCameraFeeds();
    renderSpaceList();
    renderSpaceDetail();
    renderForms();
    renderSelectors();
    renderZoneList();
    renderEditor();
    renderZoneEditor();
}

function renderMetrics() {
    const summary = appState.state.summary;
    const items = [
        ["Камеры", summary.cameras],
        ["Парковки", summary.spaces.length],
        ["Места", summary.total_parking_zones],
        ["Свободно", summary.free_zones],
        ["Занято", summary.occupied_zones]
    ];
    nodes.metricsGrid.innerHTML = items
        .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
        .join("");
}

function renderCameraFeeds() {
    if (!appState.state.cameras.length) {
        nodes.cameraFeeds.innerHTML = `<div class="empty-state">Камеры не добавлены</div>`;
        return;
    }

    nodes.cameraFeeds.innerHTML = appState.state.cameras
        .map((camera) => {
            const spaces = appState.state.spaces.filter((space) => space.camera_ids.includes(camera.id));
            return `
                <article class="feed-card">
                    <div class="feed-frame">
                        <img src="/camera/${camera.id}/snapshot.svg?t=${Date.now()}" alt="${escapeHtml(camera.name)}">
                    </div>
                    <div class="feed-meta">
                        <div>
                            <strong>${escapeHtml(camera.name)}</strong>
                            <span>${escapeHtml(camera.rtsp_url)}</span>
                        </div>
                        <span>${spaces.length} парковок</span>
                    </div>
                </article>
            `;
        })
        .join("");
}

function renderSpaceList() {
    if (!appState.state.spaces.length) {
        nodes.spaceList.innerHTML = `<div class="empty-state">Парковки не созданы</div>`;
        return;
    }

    nodes.spaceList.innerHTML = appState.state.spaces
        .map((space) => {
            const summary = appState.state.summary.spaces.find((item) => item.space_id === space.id);
            return `
                <button class="space-row ${space.id === appState.selectedSpaceId ? "active" : ""}" data-space-id="${space.id}" type="button">
                    <div class="row-title">
                        <span>${escapeHtml(space.name)}</span>
                        <span class="badge green">${summary?.free_zones ?? 0}</span>
                    </div>
                    <div class="row-meta">${summary?.occupied_zones ?? 0} занято · ${summary?.parking_zones ?? 0} мест</div>
                </button>
            `;
        })
        .join("");
}

function renderSpaceDetail() {
    const space = getSelectedSpace();
    if (!space) {
        nodes.spaceDetail.innerHTML = "";
        return;
    }
    const summary = appState.state.summary.spaces.find((item) => item.space_id === space.id);
    nodes.spaceDetail.innerHTML = `
        <div class="detail-grid">
            <div class="detail-cell"><span>Свободно</span><strong>${summary.free_zones}</strong></div>
            <div class="detail-cell"><span>Занято</span><strong>${summary.occupied_zones}</strong></div>
            <div class="detail-cell"><span>Запрещено</span><strong>${summary.forbidden_zones}</strong></div>
            <div class="detail-cell"><span>Камеры</span><strong>${space.camera_ids.length}</strong></div>
        </div>
    `;
}

function renderForms() {
    nodes.spaceCameraChoices.innerHTML = appState.state.cameras.length
        ? appState.state.cameras
              .map(
                  (camera) => `
                    <label class="checkbox-row">
                        <input type="checkbox" name="camera_ids" value="${camera.id}">
                        ${escapeHtml(camera.name)}
                    </label>
                `
              )
              .join("")
        : `<div class="row-meta">Нет камер</div>`;

    const settingsForm = document.getElementById("settingsForm");
    if (!settingsForm.contains(document.activeElement)) {
        settingsForm.elements.occupancy_interval_seconds.value = appState.state.settings.occupancy_interval_seconds;
        settingsForm.elements.yolo_model.value = appState.state.settings.yolo_model || "";
    }
}

function renderSelectors() {
    nodes.spaceSelect.innerHTML = appState.state.spaces
        .map((space) => `<option value="${space.id}">${escapeHtml(space.name)}</option>`)
        .join("");
    nodes.cameraSelect.innerHTML = appState.state.cameras
        .map((camera) => `<option value="${camera.id}">${escapeHtml(camera.name)}</option>`)
        .join("");
    nodes.spaceSelect.value = appState.selectedSpaceId || "";
    nodes.cameraSelect.value = appState.selectedCameraId || "";
}

function renderZoneList() {
    const space = getSelectedSpace();
    if (!space) {
        nodes.zoneList.innerHTML = `<div class="empty-state">Нет парковки</div>`;
        return;
    }
    if (!space.zones.length) {
        nodes.zoneList.innerHTML = `<div class="empty-state">Нет разметки</div>`;
        return;
    }

    nodes.zoneList.innerHTML = space.zones
        .map((zone) => {
            const badgeClass = zone.kind === "forbidden" ? "amber" : zone.occupied ? "red" : "green";
            const camera = appState.state.cameras.find((item) => item.id === zone.camera_id);
            return `
                <button class="zone-row ${zone.id === appState.selectedZoneId ? "active" : ""}" data-zone-id="${zone.id}" type="button">
                    <div class="row-title">
                        <span>${zoneLabel(zone)}</span>
                        <span class="badge ${badgeClass}">${zone.kind === "forbidden" ? "X" : "P"}</span>
                    </div>
                    <div class="row-meta">${camera ? escapeHtml(camera.name) : "Все камеры"} · ${zone.width.toFixed(1)} x ${zone.height.toFixed(1)}</div>
                </button>
            `;
        })
        .join("");
}

function renderEditor() {
    const camera = getSelectedCamera();
    const space = getSelectedSpace();
    if (!camera || !space) {
        nodes.editorFrame.removeAttribute("src");
        nodes.editorZones.innerHTML = "";
        return;
    }

    nodes.editorFrame.src = `/camera/${camera.id}/snapshot.svg?t=${Date.now()}`;
    nodes.editorZones.innerHTML = space.zones
        .filter((zone) => !zone.camera_id || zone.camera_id === camera.id)
        .map((zone) => {
            const classes = [
                "editor-zone",
                zone.kind === "forbidden" ? "forbidden" : "",
                zone.occupied ? "occupied" : "",
                zone.vehicle_present && !zone.occupied ? "detecting" : "",
                zone.id === appState.selectedZoneId ? "active" : ""
            ]
                .filter(Boolean)
                .join(" ");
            return `
                <div class="${classes}" data-zone-id="${zone.id}" style="left:${zone.x}%; top:${zone.y}%; width:${zone.width}%; height:${zone.height}%;">
                    ${zoneLabel(zone)}
                </div>
            `;
        })
        .join("");
}

function renderZoneEditor() {
    const zone = getSelectedZone();
    const empty = nodes.zoneEditor.querySelector(".zone-editor-empty");
    if (!zone) {
        empty.classList.remove("hidden");
        nodes.zoneEditorFields.classList.add("hidden");
        return;
    }

    empty.classList.add("hidden");
    nodes.zoneEditorFields.classList.remove("hidden");
    if (!nodes.zoneEditor.contains(document.activeElement)) {
        nodes.zoneEditor.elements.kind.value = zone.kind;
        nodes.zoneEditor.elements.x.value = zone.x;
        nodes.zoneEditor.elements.y.value = zone.y;
        nodes.zoneEditor.elements.width.value = zone.width;
        nodes.zoneEditor.elements.height.value = zone.height;
    }
    nodes.vehicleToggle.textContent = zone.vehicle_present ? "Скрыть авто" : "Авто";
    nodes.vehicleToggle.disabled = zone.kind !== "parking";
}

function getSelectedSpace() {
    return appState.state?.spaces.find((space) => space.id === appState.selectedSpaceId) || null;
}

function getSelectedCamera() {
    return appState.state?.cameras.find((camera) => camera.id === appState.selectedCameraId) || null;
}

function getSelectedZone() {
    const space = getSelectedSpace();
    return space?.zones.find((zone) => zone.id === appState.selectedZoneId) || null;
}

function zoneLabel(zone) {
    if (zone.kind === "forbidden") {
        return `X${zone.number}`;
    }
    return zone.occupied_number ? `P${zone.number} #${zone.occupied_number}` : `P${zone.number}`;
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    return new Date(value).toLocaleString("ru-RU");
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function viewportPoint(event) {
    const rect = nodes.editorViewport.getBoundingClientRect();
    return {
        x: clamp(((event.clientX - rect.left) / rect.width) * 100, 0, 100),
        y: clamp(((event.clientY - rect.top) / rect.height) * 100, 0, 100)
    };
}

document.querySelectorAll(".mode-tab").forEach((button) => {
    button.addEventListener("click", () => {
        appState.view = button.dataset.view;
        document.querySelectorAll(".mode-tab").forEach((tab) => tab.classList.toggle("active", tab === button));
        document.getElementById("workView").classList.toggle("active", appState.view === "work");
        document.getElementById("setupView").classList.toggle("active", appState.view === "setup");
    });
});

document.getElementById("refreshButton").addEventListener("click", () => loadState());

document.getElementById("cameraForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
        await api("/api/cameras", {
            method: "POST",
            body: JSON.stringify({
                name: form.elements.name.value,
                rtsp_url: form.elements.rtsp_url.value
            })
        });
        form.reset();
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

document.getElementById("spaceForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const cameraIds = [...form.querySelectorAll("input[name='camera_ids']:checked")].map((input) => input.value);
    try {
        await api("/api/spaces", {
            method: "POST",
            body: JSON.stringify({ name: form.elements.name.value, camera_ids: cameraIds })
        });
        form.reset();
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

document.getElementById("settingsForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
        await api("/api/settings", {
            method: "PATCH",
            body: JSON.stringify({
                occupancy_interval_seconds: Number(form.elements.occupancy_interval_seconds.value),
                yolo_model: form.elements.yolo_model.value
            })
        });
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

document.querySelectorAll(".tool-button").forEach((button) => {
    button.addEventListener("click", () => {
        appState.zoneKind = button.dataset.zoneKind;
        document.querySelectorAll(".tool-button").forEach((item) => item.classList.toggle("active", item === button));
    });
});

nodes.spaceSelect.addEventListener("change", () => {
    appState.selectedSpaceId = nodes.spaceSelect.value;
    appState.selectedZoneId = getSelectedSpace()?.zones?.[0]?.id || null;
    render();
});

nodes.cameraSelect.addEventListener("change", () => {
    appState.selectedCameraId = nodes.cameraSelect.value;
    render();
});

nodes.spaceList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-space-id]");
    if (!row) {
        return;
    }
    appState.selectedSpaceId = row.dataset.spaceId;
    appState.selectedZoneId = getSelectedSpace()?.zones?.[0]?.id || null;
    render();
});

nodes.zoneList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-zone-id]");
    if (!row) {
        return;
    }
    appState.selectedZoneId = row.dataset.zoneId;
    render();
});

nodes.editorViewport.addEventListener("click", async (event) => {
    if (event.target.closest(".editor-zone") || appState.drag) {
        return;
    }
    const space = getSelectedSpace();
    const camera = getSelectedCamera();
    if (!space || !camera) {
        return;
    }
    const point = viewportPoint(event);
    try {
        const payload = {
            kind: appState.zoneKind,
            camera_id: camera.id,
            x: clamp(point.x - 9, 0, 82),
            y: clamp(point.y - 6, 0, 88),
            width: 18,
            height: 12
        };
        const result = await api(`/api/spaces/${space.id}/zones`, {
            method: "POST",
            body: JSON.stringify(payload)
        });
        appState.selectedZoneId = result.zone.id;
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

nodes.editorZones.addEventListener("pointerdown", (event) => {
    const zoneElement = event.target.closest(".editor-zone");
    if (!zoneElement) {
        return;
    }
    const zone = getSelectedSpace()?.zones.find((item) => item.id === zoneElement.dataset.zoneId);
    if (!zone) {
        return;
    }
    appState.selectedZoneId = zone.id;
    appState.drag = {
        zoneId: zone.id,
        startX: event.clientX,
        startY: event.clientY,
        originalX: zone.x,
        originalY: zone.y,
        width: zone.width,
        height: zone.height,
        rect: nodes.editorViewport.getBoundingClientRect()
    };
    zoneElement.setPointerCapture(event.pointerId);
    renderZoneList();
    renderZoneEditor();
});

document.addEventListener("pointermove", (event) => {
    if (!appState.drag) {
        return;
    }
    const zone = getSelectedSpace()?.zones.find((item) => item.id === appState.drag.zoneId);
    if (!zone) {
        return;
    }
    const dx = ((event.clientX - appState.drag.startX) / appState.drag.rect.width) * 100;
    const dy = ((event.clientY - appState.drag.startY) / appState.drag.rect.height) * 100;
    zone.x = clamp(appState.drag.originalX + dx, 0, 100 - appState.drag.width);
    zone.y = clamp(appState.drag.originalY + dy, 0, 100 - appState.drag.height);
    renderEditor();
    renderZoneEditor();
});

document.addEventListener("pointerup", async () => {
    if (!appState.drag) {
        return;
    }
    const drag = appState.drag;
    appState.drag = null;
    const zone = getSelectedSpace()?.zones.find((item) => item.id === drag.zoneId);
    if (!zone) {
        return;
    }
    try {
        await api(`/api/zones/${zone.id}`, {
            method: "PATCH",
            body: JSON.stringify({ x: zone.x, y: zone.y })
        });
        await loadState(true);
    } catch (error) {
        showStatus(error.message, true);
        await loadState(true);
    }
});

nodes.zoneEditor.addEventListener("submit", async (event) => {
    event.preventDefault();
    const zone = getSelectedZone();
    if (!zone) {
        return;
    }
    const form = event.currentTarget;
    try {
        await api(`/api/zones/${zone.id}`, {
            method: "PATCH",
            body: JSON.stringify({
                kind: form.elements.kind.value,
                x: Number(form.elements.x.value),
                y: Number(form.elements.y.value),
                width: Number(form.elements.width.value),
                height: Number(form.elements.height.value)
            })
        });
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

nodes.vehicleToggle.addEventListener("click", async () => {
    const zone = getSelectedZone();
    if (!zone || zone.kind !== "parking") {
        return;
    }
    try {
        await api(`/api/zones/${zone.id}/vehicle`, {
            method: "POST",
            body: JSON.stringify({ present: !zone.vehicle_present })
        });
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

nodes.deleteZone.addEventListener("click", async () => {
    const zone = getSelectedZone();
    if (!zone) {
        return;
    }
    try {
        await api(`/api/zones/${zone.id}`, { method: "DELETE" });
        appState.selectedZoneId = null;
        await loadState();
    } catch (error) {
        showStatus(error.message, true);
    }
});

loadState();
setInterval(() => {
    if (!appState.drag) {
        loadState(true);
    }
}, 2500);
