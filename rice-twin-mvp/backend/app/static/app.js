import * as maplibregl from "/static/vendor/maplibre-gl.mjs";

const state = {
  map: null,
  mapLoaded: false,
  plot: null,
  activities: [],
  imagery: [],
  quality: null,
  carbon: null,
  seasons: [],
  imageryVisibility: new Map(),
  selectedImageryId: null,
  selectedImageryMode: "stored",
};

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch (_) {
      // Keep HTTP fallback message.
    }
    throw new Error(message);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response;
}

function setApiStatus(mode, text) {
  const dot = qs(".status-dot");
  dot.classList.remove("online", "offline");
  if (mode) dot.classList.add(mode);
  qs("#apiStatus").textContent = text;
}

function formatDate(value) {
  if (!value) return "ไม่ระบุวันเวลา";
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}

function toLocalDateTimeInput(date = new Date()) {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

function formatFileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function inferDateFromFilename(filename) {
  const match = filename.match(/(20\d{2})[-_]?(\d{2})[-_]?(\d{2})/);
  if (!match) return null;
  const date = new Date(`${match[1]}-${match[2]}-${match[3]}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function renderModeLabel(mode) {
  return {
    auto: "เลือก band จาก metadata",
    sentinel2_true_color: "Sentinel-2 สีธรรมชาติ 3/2/1",
    grayscale: "ขาวดำจาก band 1",
    rgb_123: "RGB band 1/2/3",
    custom: `กำหนดเอง ${qs("#redBand").value}/${qs("#greenBand").value}/${qs("#blueBand").value}`,
  }[mode] || "เลือก band อัตโนมัติ";
}

function clearImagerySelection() {
  qs("#imageryFile").value = "";
  qs("#uploadReview").hidden = true;
  qs("#uploadImageryButton").disabled = true;
  qs("#imageryMessage").textContent = "";
}

function initializeTabs() {
  qsa(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      qsa(".tab").forEach((item) => item.classList.remove("active"));
      qsa(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      qs(`#tab-${button.dataset.tab}`).classList.add("active");
      if (state.map) setTimeout(() => state.map.resize(), 40);
    });
  });
}

function initializeMap(config) {
  state.map = new maplibregl.Map({
    container: "map",
    center: config.map_center,
    zoom: config.map_zoom,
    style: {
      version: 8,
      sources: {
        satellite: {
          type: "raster",
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          attribution: "Tiles © Esri",
        },
        osm: {
          type: "raster",
          tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap contributors",
        },
      },
      layers: [
        { id: "basemap-satellite", type: "raster", source: "satellite" },
        { id: "basemap-streets", type: "raster", source: "osm", layout: { visibility: "none" } },
      ],
    },
  });
  state.map.addControl(new maplibregl.NavigationControl(), "top-right");
  state.map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

  return new Promise((resolve, reject) => {
    state.map.once("load", () => {
      state.mapLoaded = true;
      resolve();
    });
    state.map.once("error", (event) => {
      if (!state.mapLoaded) reject(event.error || new Error("Map failed to load"));
    });
  });
}

function geometryBounds(geometry) {
  const coordinates = geometry.coordinates.flat(Infinity);
  const bounds = new maplibregl.LngLatBounds();
  for (let index = 0; index < coordinates.length; index += 2) {
    bounds.extend([coordinates[index], coordinates[index + 1]]);
  }
  return bounds;
}

function addPlotToMap(featureCollection) {
  if (state.map.getSource("plots")) {
    state.map.getSource("plots").setData(featureCollection);
    return;
  }

  state.map.addSource("plots", { type: "geojson", data: featureCollection });
  state.map.addLayer({
    id: "plot-fill",
    type: "fill",
    source: "plots",
    paint: {
      "fill-color": "#24734a",
      "fill-opacity": 0.22,
    },
  });
  state.map.addLayer({
    id: "plot-outline",
    type: "line",
    source: "plots",
    paint: {
      "line-color": "#155336",
      "line-width": 3,
    },
  });
  state.map.on("mouseenter", "plot-fill", () => {
    state.map.getCanvas().style.cursor = "pointer";
  });
  state.map.on("mouseleave", "plot-fill", () => {
    state.map.getCanvas().style.cursor = "";
  });
  state.map.on("click", "plot-fill", (event) => {
    const feature = event.features?.[0];
    if (!feature) return;
    new maplibregl.Popup()
      .setLngLat(event.lngLat)
      .setHTML(
        `<div class="popup-title">${escapeHtml(feature.properties.name)}</div>
         <div class="popup-meta">${escapeHtml(feature.properties.id)} · ${escapeHtml(feature.properties.area_rai)} ไร่</div>`
      )
      .addTo(state.map);
  });

  const first = featureCollection.features[0];
  if (first) {
    state.map.fitBounds(geometryBounds(first.geometry), {
      padding: { top: 70, right: 70, bottom: 70, left: 70 },
      maxZoom: 17,
      duration: 850,
    });
  }
}

function renderTwin() {
  if (!state.plot) return;
  const p = state.plot.properties;
  qs("#plotName").textContent = p.name;
  qs("#plotId").textContent = p.id;
  qs("#plotCoordinate").textContent = `${Number(p.center_lat).toFixed(6)}, ${Number(p.center_lon).toFixed(6)}`;
  qs("#waterLevel").textContent = `${Number(p.water_level_cm).toFixed(1)} ซม.`;
  qs("#awdCycle").textContent = `รอบ ${p.awd_cycle}`;
  qs("#dryDays").textContent = `${p.dry_days} วัน`;
  qs("#areaRai").textContent = Number(p.area_rai).toFixed(1);
  qs("#cropStage").textContent = p.crop_stage;
  qs("#waterState").textContent = p.water_state;
  qs("#yieldRisk").textContent = p.yield_risk;
  qs("#mrvConfidence").textContent = p.mrv_confidence;
  qs("#recommendation").textContent = p.recommendation;
  qs("#confidenceText").textContent = `${p.data_confidence_score}/100`;
  qs("#confidenceBar").style.width = `${p.data_confidence_score}%`;
}

function renderQuality() {
  if (!state.quality) return;
  qs("#qualityScore").textContent = `${state.quality.score}/100`;
  qs("#qualityChecks").innerHTML = state.quality.components.map((item) => `
    <article class="check-item ${item.passed ? "pass" : "fail"}">
      <span class="check-icon">${item.passed ? "✓" : "!"}</span>
      <div><strong>${escapeHtml(item.explanation)}</strong>
      <small>${escapeHtml(item.check_id)} · ${item.score}/${item.weight} คะแนน</small></div>
    </article>`).join("");
}

function renderCarbon() {
  if (!state.carbon) return;
  qs("#carbonMessage").textContent = state.carbon.message;
  qs("#methodologyVersion").textContent = state.carbon.methodology_version || "ยังไม่กำหนด";
  qs("#verificationStatus").textContent = state.carbon.verification_status || "ยังไม่เริ่ม";
}

function renderActivities() {
  const container = qs("#activityTimeline");
  qs("#activityCount").textContent = `${state.activities.length} รายการ`;
  if (!state.activities.length) {
    container.innerHTML = '<div class="empty-state">ยังไม่มีกิจกรรมในแปลงนี้</div>';
    renderWaterChart();
    return;
  }

  container.innerHTML = state.activities
    .map(
      (item) => `
        <article class="timeline-item">
          <span class="timeline-dot"></span>
          <h4>${escapeHtml(item.activity_type)}</h4>
          <div class="timeline-meta">${escapeHtml(formatDate(item.occurred_at))} · ${escapeHtml(item.source)}</div>
          ${item.note ? `<p>${escapeHtml(item.note)}</p>` : ""}
          ${item.water_level_cm !== null ? `<span class="timeline-value">ระดับน้ำ ${Number(item.water_level_cm).toFixed(1)} ซม.</span>` : ""}
        </article>`
    )
    .join("");
  renderWaterChart();
}

function renderWaterChart() {
  const svg = qs("#waterChart");
  const points = state.activities
    .filter((item) => item.water_level_cm !== null)
    .slice()
    .sort((a, b) => new Date(a.occurred_at) - new Date(b.occurred_at));

  if (!points.length) {
    svg.innerHTML = '<text x="260" y="78" text-anchor="middle" fill="#66736c" font-size="12">ยังไม่มีข้อมูลระดับน้ำ</text>';
    return;
  }

  const width = 520;
  const height = 150;
  const padding = { left: 36, right: 14, top: 14, bottom: 26 };
  const values = points.map((item) => Number(item.water_level_cm));
  let min = Math.min(...values, 0);
  let max = Math.max(...values, 0);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const span = max - min;
  min -= span * 0.15;
  max += span * 0.15;

  const x = (index) =>
    padding.left +
    (points.length === 1 ? (width - padding.left - padding.right) / 2 : (index / (points.length - 1)) * (width - padding.left - padding.right));
  const y = (value) => padding.top + ((max - value) / (max - min)) * (height - padding.top - padding.bottom);
  const linePoints = points.map((item, index) => `${x(index)},${y(Number(item.water_level_cm))}`).join(" ");
  const zeroY = y(0);

  svg.innerHTML = `
    <line x1="${padding.left}" y1="${zeroY}" x2="${width - padding.right}" y2="${zeroY}" stroke="#b8c3bc" stroke-dasharray="4 4" />
    <text x="4" y="${zeroY + 4}" fill="#66736c" font-size="10">0 cm</text>
    <polyline points="${linePoints}" fill="none" stroke="#24734a" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    ${points
      .map(
        (item, index) => `
          <circle cx="${x(index)}" cy="${y(Number(item.water_level_cm))}" r="4" fill="#ffffff" stroke="#155336" stroke-width="2" />
          <text x="${x(index)}" y="${height - 7}" text-anchor="middle" fill="#66736c" font-size="9">${new Intl.DateTimeFormat("th-TH", { day: "numeric", month: "short", timeZone: "Asia/Bangkok" }).format(new Date(item.occurred_at))}</text>`
      )
      .join("")}
  `;
}

function imageryLayerId(id) {
  return `imagery-layer-${id}`;
}

function imagerySourceId(id) {
  return `imagery-source-${id}`;
}

function addImageryLayer(item, visible = false, renderMode = "stored") {
  const sourceId = imagerySourceId(item.id);
  const layerId = imageryLayerId(item.id);
  if (state.map.getLayer(layerId)) state.map.removeLayer(layerId);
  if (state.map.getSource(sourceId)) state.map.removeSource(sourceId);

  const [west, south, east, north] = item.bounds_wgs84;
  state.map.addSource(sourceId, {
    type: "image",
    url: `${item.preview_url}?render_mode=${encodeURIComponent(renderMode)}&v=${encodeURIComponent(item.uploaded_at)}`,
    coordinates: [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ],
  });
  state.map.addLayer(
    {
      id: layerId,
      type: "raster",
      source: sourceId,
      layout: { visibility: visible ? "visible" : "none" },
      paint: { "raster-opacity": Number(qs("#imageryOpacity").value) },
    },
    state.map.getLayer("plot-fill") ? "plot-fill" : undefined
  );
  state.imageryVisibility.set(item.id, visible);
}

function setImageryVisibility(id, visible) {
  const layerId = imageryLayerId(id);
  if (state.map.getLayer(layerId)) {
    state.map.setLayoutProperty(layerId, "visibility", visible ? "visible" : "none");
  }
  state.imageryVisibility.set(id, visible);
}

const RICE_IMAGERY_MODES = {
  rice_true_color: {
    label: "สีธรรมชาติ",
    help: "ใช้ตรวจเมฆ แนวคันนา และสภาพแปลงโดยรวม",
  },
  rice_false_color: {
    label: "พืชพรรณแบบสีเท็จ",
    help: "ใช้ NIR/แดง/เขียว เพื่อเน้นความแตกต่างของพืชและพื้นที่น้ำ",
  },
  rice_ndvi: {
    label: "NDVI — ความเขียวของข้าว",
    help: "สีเขียวเข้มหมายถึงทรงพุ่มเขียวมากขึ้น ใช้ติดตามการเจริญเติบโต ไม่ใช่ผลผลิตโดยตรง",
  },
  rice_evi: {
    label: "EVI — การเติบโตของทรงพุ่ม",
    help: "เหมาะสำหรับติดตามพืชที่มีทรงพุ่มหนาแน่น และช่วยลดผลกระทบจากพื้นดินบางส่วน",
  },
  rice_lswi: {
    label: "LSWI — ความชื้นในแปลงข้าว",
    help: "ใช้ติดตามความชื้นของพืชและสัญญาณน้ำช่วงน้ำขังหรือปักดำ",
  },
  rice_ndwi: {
    label: "NDWI — น้ำและความเปียกชื้น",
    help: "ช่วยเน้นน้ำหรือความเปียกชื้นในแปลง ควรอ่านร่วมกับข้อมูลภาคสนาม",
  },
  rice_sar_vv: {
    label: "Radar VV — ผิวน้ำและโครงสร้างแปลง",
    help: "Sentinel-1 มองผ่านเมฆได้ ใช้ติดตามการเปลี่ยนแปลงของผิวน้ำและโครงสร้างพืช",
  },
  rice_sar_vh: {
    label: "Radar VH — โครงสร้างต้นข้าว",
    help: "ไวต่อการกระเจิงจากลำต้นและทรงพุ่ม เหมาะกับการติดตามการเปลี่ยนแปลงตามระยะปลูก",
  },
  rice_sar_diff: {
    label: "Radar VH−VV — ความต่างของสัญญาณ",
    help: "ใช้ดูความเปลี่ยนแปลงร่วมกันของน้ำและโครงสร้างข้าว ไม่ใช่การจำแนกอัตโนมัติ",
  },
  stored: {
    label: "ภาพตามค่าที่อัปโหลด",
    help: "แสดง preview ตาม band ที่ระบบเลือกตอนอัปโหลด",
  },
};

function availableRiceModes(item) {
  if (!item) return ["stored"];
  const satellite = item.source_metadata?.satellite;
  if (satellite === "Sentinel-2") {
    return ["rice_true_color", "rice_ndvi", "rice_evi", "rice_lswi", "rice_ndwi", "rice_false_color"];
  }
  if (satellite === "Sentinel-1") {
    return ["rice_sar_vv", "rice_sar_vh", "rice_sar_diff"];
  }
  return ["stored"];
}

function imageryOptionLabel(item) {
  const satellite = item.source_metadata?.satellite || "ภาพอัปโหลด";
  const date = new Intl.DateTimeFormat("th-TH", {
    day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Bangkok",
  }).format(new Date(item.captured_at || item.uploaded_at));
  const cloud = item.source_metadata?.cloud_cover_percent;
  return `${date} · ${satellite}${Number.isFinite(cloud) ? ` · เมฆ ${cloud.toFixed(0)}%` : ""}`;
}

function applyImagerySelection({ fit = false } = {}) {
  const item = state.imagery.find((candidate) => candidate.id === state.selectedImageryId);
  if (!item) return;
  state.imagery.forEach((candidate) => {
    if (candidate.id !== item.id) setImageryVisibility(candidate.id, false);
  });
  const mode = state.selectedImageryMode;
  addImageryLayer(item, qs("#imageryVisible").checked, mode);
  qs("#imageryModeHelp").textContent = RICE_IMAGERY_MODES[mode]?.help || "";
  if (fit) {
    const [west, south, east, north] = item.bounds_wgs84;
    state.map.fitBounds([[west, south], [east, north]], { padding: 70, maxZoom: 17 });
  }
}

function renderImagery() {
  const container = qs("#imageryList");
  qs("#imageryCount").textContent = `${state.imagery.length} ภาพ`;
  if (!state.imagery.length) {
    container.textContent = "ยังไม่มีภาพดาวเทียม อัปโหลด GeoTIFF เพื่อสร้าง overlay";
    qs("#imagerySceneSelect").innerHTML = '<option>ยังไม่มีภาพ</option>';
    qs("#imageryModeSelect").innerHTML = '<option>—</option>';
    return;
  }
  const sorted = state.imagery.slice().sort(
    (a, b) => new Date(b.captured_at || b.uploaded_at) - new Date(a.captured_at || a.uploaded_at)
  );
  if (!state.selectedImageryId || !state.imagery.some((item) => item.id === state.selectedImageryId)) {
    state.selectedImageryId = (
      sorted.find((item) => item.source === "downloaded_catalog") || sorted[0]
    ).id;
  }
  qs("#imagerySceneSelect").innerHTML = sorted.map(
    (item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(imageryOptionLabel(item))}</option>`
  ).join("");
  qs("#imagerySceneSelect").value = state.selectedImageryId;
  const selected = state.imagery.find((item) => item.id === state.selectedImageryId);
  const modes = availableRiceModes(selected);
  if (!modes.includes(state.selectedImageryMode)) state.selectedImageryMode = modes[0];
  qs("#imageryModeSelect").innerHTML = modes.map(
    (mode) => `<option value="${mode}">${escapeHtml(RICE_IMAGERY_MODES[mode].label)}</option>`
  ).join("");
  qs("#imageryModeSelect").value = state.selectedImageryMode;
  const sentinelCount = state.imagery.filter((item) => item.source === "downloaded_catalog").length;
  container.textContent = `${sentinelCount} ภาพจากคลัง Sentinel · ${state.imagery.length - sentinelCount} ภาพอัปโหลด`;
  applyImagerySelection();
}

async function loadPlotData() {
  const plots = await api("/api/plots");
  if (!plots.features?.length) throw new Error("No plots are registered");
  state.plot = plots.features[0];
  addPlotToMap(plots);
  renderTwin();

  const plotId = state.plot.properties.id;
  const [activities, imagery, quality, carbon, seasons] = await Promise.all([
    api(`/api/plots/${encodeURIComponent(plotId)}/activities`),
    api(`/api/imagery?plot_id=${encodeURIComponent(plotId)}`),
    api(`/api/plots/${encodeURIComponent(plotId)}/data-quality`),
    api(`/api/plots/${encodeURIComponent(plotId)}/carbon`),
    api(`/api/plots/${encodeURIComponent(plotId)}/crop-seasons`),
  ]);
  state.activities = activities;
  state.imagery = imagery;
  state.quality = quality;
  state.carbon = carbon;
  state.seasons = seasons;
  renderActivities();
  renderQuality();
  renderCarbon();

  renderImagery();
}

async function refreshCurrentPlot() {
  if (!state.plot) return;
  const plotId = state.plot.properties.id;
  state.plot = await api(`/api/plots/${encodeURIComponent(plotId)}`);
  state.activities = await api(`/api/plots/${encodeURIComponent(plotId)}/activities`);
  state.quality = await api(`/api/plots/${encodeURIComponent(plotId)}/data-quality`);
  renderTwin();
  renderActivities();
  renderQuality();
}

function initializeForms() {
  qs("#activityTime").value = toLocalDateTimeInput();

  qs("#basemapSelect").addEventListener("change", (event) => {
    if (!state.mapLoaded) return;
    const satellite = event.target.value === "satellite";
    state.map.setLayoutProperty("basemap-satellite", "visibility", satellite ? "visible" : "none");
    state.map.setLayoutProperty("basemap-streets", "visibility", satellite ? "none" : "visible");
  });

  qs("#imagerySceneSelect").addEventListener("change", (event) => {
    state.selectedImageryId = event.target.value;
    const item = state.imagery.find((candidate) => candidate.id === state.selectedImageryId);
    state.selectedImageryMode = availableRiceModes(item)[0];
    renderImagery();
    applyImagerySelection({ fit: true });
  });

  qs("#imageryModeSelect").addEventListener("change", (event) => {
    state.selectedImageryMode = event.target.value;
    applyImagerySelection();
  });

  qs("#imageryVisible").addEventListener("change", (event) => {
    if (state.selectedImageryId) {
      setImageryVisibility(state.selectedImageryId, event.target.checked);
    }
  });

  qs("#activityForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = qs("#activityMessage");
    const button = event.submitter;
    message.className = "form-message";
    message.textContent = "กำลังบันทึก";
    button.disabled = true;

    try {
      const waterRaw = qs("#activityWater").value;
      const payload = {
        activity_type: qs("#activityType").value,
        occurred_at: new Date(qs("#activityTime").value).toISOString(),
        note: qs("#activityNote").value || null,
        water_level_cm: waterRaw === "" ? null : Number(waterRaw),
        source: "web_mvp",
        evidence: { record_type: "manual_entry" },
      };
      await api(`/api/plots/${encodeURIComponent(state.plot.properties.id)}/activities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      qs("#activityNote").value = "";
      qs("#activityWater").value = "";
      qs("#activityTime").value = toLocalDateTimeInput();
      message.className = "form-message success";
      message.textContent = "บันทึกกิจกรรมแล้ว";
      await refreshCurrentPlot();
    } catch (error) {
      message.className = "form-message error";
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  qs("#evaluateButton").addEventListener("click", async () => {
    const button = qs("#evaluateButton");
    const message = qs("#evaluationMessage");
    button.disabled = true;
    message.textContent = "กำลังประเมินกฎสาธิต";
    try {
      const result = await api(`/api/plots/${encodeURIComponent(state.plot.properties.id)}/evaluate`, {
        method: "POST",
      });
      qs("#ruleVersion").textContent = result.evaluations[0]?.rule_version || "demo rules";
      message.className = "form-message success";
      message.textContent = result.evaluations[0]?.explanation || "ประเมินแล้ว";
      await refreshCurrentPlot();
    } catch (error) {
      message.className = "form-message error";
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  qs("#simulateButton").addEventListener("click", async () => {
    const button = qs("#simulateButton");
    button.disabled = true;
    try {
      const p = state.plot.properties;
      const nextLevel = Number(p.water_level_cm) - 1;
      await api(`/api/plots/${encodeURIComponent(p.id)}/activities`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activity_type: "วัดระดับน้ำ",
          occurred_at: new Date().toISOString(),
          note: "ข้อมูลจำลองจากปุ่มใน MVP",
          water_level_cm: nextLevel,
          source: "simulation",
          evidence: { simulated: true },
        }),
      });
      await api(`/api/plots/${encodeURIComponent(p.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dry_days: Number(p.dry_days) + 1,
          water_state: "ช่วงปล่อยแห้ง",
        }),
      });
      await refreshCurrentPlot();
    } catch (error) {
      window.alert(`จำลองข้อมูลไม่สำเร็จ: ${error.message}`);
    } finally {
      button.disabled = false;
    }
  });

  qs("#imageryFile").addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      clearImagerySelection();
      return;
    }
    const inferredDate = inferDateFromFilename(file.name);
    qs("#selectedFile").textContent = file.name;
    qs("#selectedFileSize").textContent = formatFileSize(file.size);
    qs("#reviewDate").textContent = inferredDate
      ? new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeZone: "UTC" }).format(inferredDate)
      : "อ่านจาก metadata / ระบุภายหลัง";
    qs("#reviewBands").textContent = renderModeLabel(qs("#renderMode").value);
    qs("#uploadReview").hidden = false;
    qs("#uploadImageryButton").disabled = false;
  });

  qs("#clearImageryFile").addEventListener("click", clearImagerySelection);

  qs("#renderMode").addEventListener("change", (event) => {
    qs("#customBandFields").hidden = event.target.value !== "custom";
    qs("#reviewBands").textContent = renderModeLabel(event.target.value);
  });

  ["#redBand", "#greenBand", "#blueBand"].forEach((selector) => {
    qs(selector).addEventListener("input", () => {
      if (qs("#renderMode").value === "custom") {
        qs("#reviewBands").textContent = renderModeLabel("custom");
      }
    });
  });

  qs("#imageryForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = qs("#imageryFile").files?.[0];
    const message = qs("#imageryMessage");
    const button = event.submitter;
    if (!file) return;

    message.className = "form-message";
    message.textContent = "กำลังอัปโหลดและประมวลผล raster";
    button.disabled = true;

    try {
      const form = new FormData();
      form.append("plot_id", state.plot.properties.id);
      form.append("file", file);
      const renderMode = qs("#renderMode").value;
      form.append("render_mode", renderMode);
      if (renderMode === "custom") {
        form.append("red_band", qs("#redBand").value);
        form.append("green_band", qs("#greenBand").value);
        form.append("blue_band", qs("#blueBand").value);
      }
      if (qs("#capturedAt").value) {
        form.append("captured_at", new Date(qs("#capturedAt").value).toISOString());
      }

      const item = await api("/api/imagery", { method: "POST", body: form });
      state.imagery.unshift(item);
      state.selectedImageryId = item.id;
      state.selectedImageryMode = "stored";
      renderImagery();
      qs("#imageryForm").reset();
      qs("#customBandFields").hidden = true;
      qs("#redBand").value = 1;
      qs("#greenBand").value = 2;
      qs("#blueBand").value = 3;
      qs("#uploadReview").hidden = true;
      qs("#uploadImageryButton").disabled = true;
      message.className = "form-message success";
      const dateText = item.captured_at ? formatDate(item.captured_at) : "ไม่ได้ระบุวันที่";
      message.textContent = `เพิ่มภาพแล้ว · ${dateText} · band ${item.render_bands.join("/")}`;

      const [west, south, east, north] = item.bounds_wgs84;
      state.map.fitBounds([[west, south], [east, north]], { padding: 70, maxZoom: 18 });
    } catch (error) {
      message.className = "form-message error";
      message.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  qs("#imageryOpacity").addEventListener("input", (event) => {
    const opacity = Number(event.target.value);
    qs("#opacityValue").textContent = `${Math.round(opacity * 100)}%`;
    state.imagery.forEach((item) => {
      const layerId = imageryLayerId(item.id);
      if (state.map.getLayer(layerId)) state.map.setPaintProperty(layerId, "raster-opacity", opacity);
    });
  });
}

async function boot() {
  initializeTabs();
  initializeForms();
  try {
    const config = await api("/api/config");
    await initializeMap(config);
    await loadPlotData();
    setApiStatus("online", "ระบบพร้อมใช้งาน");
  } catch (error) {
    console.error(error);
    setApiStatus("offline", `เชื่อมต่อไม่สำเร็จ: ${error.message}`);
  }
}

boot();
