"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type View = "overview" | "water" | "iot" | "satellite" | "evidence" | "scenarios";

const boundaryWarning =
  "DEMO-PLOT-001 is a synthetic demonstration boundary. It is not a cadastral, surveyed, legal, ownership, or officially verified plot boundary.";

const nav: { id: View; label: string; icon: string }[] = [
  { id: "overview", label: "Command Center", icon: "▦" },
  { id: "water", label: "Water & AWD", icon: "≈" },
  { id: "iot", label: "IoT Operations", icon: "⌁" },
  { id: "satellite", label: "Satellite", icon: "◇" },
  { id: "evidence", label: "Verifier Portal", icon: "✓" },
  { id: "scenarios", label: "Demo Scenarios", icon: "▶" },
];

const kpis = [
  { label: "พื้นที่ติดตาม", value: "104.5", unit: "ไร่", source: "REFERENCE" },
  { label: "แปลงใช้งาน", value: "6", unit: "แปลง", source: "DERIVED" },
  { label: "เซนเซอร์พร้อมใช้", value: "12/12", unit: "อุปกรณ์", source: "DERIVED" },
  { label: "น้ำที่ประหยัดโดยประมาณ", value: "428", unit: "m³ / 30 วัน", source: "DERIVED" },
  { label: "Data confidence", value: "91", unit: "%", source: "DERIVED" },
  { label: "MRV readiness", value: "68", unit: "%", source: "DERIVED" },
];

const devices = [
  ["WATER-LEVEL-01", "ระดับน้ำในท่อ AWD หลัก", "LoRaWAN", "92%", "-67 dBm", "ONLINE"],
  ["WATER-LEVEL-02", "ระดับน้ำสำรอง", "LoRaWAN", "89%", "-69 dBm", "WARNING"],
  ["SOIL-10", "ความชื้นดิน 10 ซม.", "LoRaWAN", "86%", "-71 dBm", "ONLINE"],
  ["SOIL-30", "ความชื้นดิน 30 ซม.", "LoRaWAN", "83%", "-73 dBm", "ONLINE"],
  ["SOIL-50", "ความชื้นดิน 50 ซม.", "LoRaWAN", "80%", "-75 dBm", "ONLINE"],
  ["RAIN-01", "มาตรวัดฝนประจำแปลง", "LoRaWAN", "77%", "-77 dBm", "ONLINE"],
  ["WEATHER-01", "สถานีอากาศขนาดเล็ก", "LoRaWAN", "74%", "-79 dBm", "ONLINE"],
  ["PUMP-01", "สถานะเครื่องสูบน้ำ", "Wi-Fi", "71%", "-81 dBm", "ONLINE"],
  ["FLOW-01", "อัตราการไหลทางน้ำเข้า", "Wi-Fi", "68%", "-83 dBm", "ONLINE"],
  ["ENERGY-01", "พลังงานเครื่องสูบน้ำ", "Wi-Fi", "65%", "-85 dBm", "ONLINE"],
  ["WATER-QUALITY-01", "คุณภาพน้ำทางน้ำเข้า", "Wi-Fi", "62%", "-87 dBm", "ONLINE"],
  ["GATE-01", "ตำแหน่งประตูน้ำ", "Wi-Fi", "59%", "-89 dBm", "ONLINE"],
];

const scenarios = [
  ["รอบ AWD ปกติ", "หยุดให้น้ำ ปล่อยระดับน้ำลด แล้วเริ่มรอบใหม่"],
  ["รอฝนตามพยากรณ์", "ชะลอการสูบน้ำ 12 ชั่วโมงเมื่อมีฝน 22 มม."],
  ["เสี่ยงแห้งเกิน", "ระดับน้ำและความชื้นต่ำกว่าค่าปลอดภัย"],
  ["ฝนหนักและน้ำท่วม", "ฝนเข้มข้นทำให้ต้องเตรียมระบายน้ำ"],
  ["เซนเซอร์ออฟไลน์", "สลับไปใช้ค่าประมาณสำรองและลด confidence"],
  ["เซนเซอร์คลาดเคลื่อน", "ค่าจากอุปกรณ์สองตัวต่างกันเกิน tolerance"],
  ["รายงานภาคสนามไม่ตรง", "แจ้งว่าให้น้ำแล้วแต่ pump และ flow ไม่ยืนยัน"],
  ["Public data ไม่ตรง", "มาตรวัดในแปลงพบฝน แต่สถานีภูมิภาคไม่พบ"],
  ["Satellite conflict", "รายงานว่าแห้งแต่ดัชนีน้ำชี้ความเปียก"],
  ["ฤดูปลูกและ MRV", "เหตุการณ์ตั้งแต่ขึ้นทะเบียนถึงตรวจความพร้อม"],
];

type SentinelSensor = "Sentinel-2" | "Sentinel-1";
type ImageryCoordinates = [[number, number], [number, number], [number, number], [number, number]];

const sentinel2Modes = [
  ["rice_true_color", "สีธรรมชาติ", "ตรวจเมฆ คันนา และสภาพผิวทั่วไป"],
  ["rice_false_color", "สีเท็จพืชพรรณ", "แยกความหนาแน่นของพืชจากพื้นดินและน้ำ"],
  ["rice_ndvi", "NDVI", "ความเขียวและ vigor ของข้าว"],
  ["rice_lswi", "LSWI", "ความชื้นในพืชและผิวดิน"],
  ["rice_ndwi", "NDWI", "candidate water และความเปียก"],
  ["rice_evi", "EVI", "พืชหนาแน่นและผลกระทบบรรยากาศ"],
];

const sentinel1Modes = [
  ["rice_sar_vv", "Radar VV", "ผิวน้ำและโครงสร้างแปลง มองผ่านเมฆได้"],
  ["rice_sar_vh", "Radar VH", "การกระเจิงจากลำต้นและทรงพุ่มข้าว"],
  ["rice_sar_diff", "Radar VH−VV", "ความเปลี่ยนแปลงร่วมกันของน้ำและโครงสร้างข้าว"],
];

const sentinel2Coordinates: ImageryCoordinates = [
  [100.26460859984597, 14.4799171060011],
  [100.28485500871204, 14.4799171060011],
  [100.28485500871204, 14.459559806312308],
  [100.26460859984597, 14.459559806312308],
];

const sentinel1Coordinates: ImageryCoordinates = [
  [100.26462000860424, 14.479836420011923],
  [100.2848653877068, 14.479836420011923],
  [100.2848653877068, 14.459659907243962],
  [100.26462000860424, 14.459659907243962],
];

const sentinelScenes: {
  id: string;
  date: string;
  iso: string;
  sensor: SentinelSensor;
  cloud?: number;
  coordinates: ImageryCoordinates;
}[] = [
  { id: "catalog-2bb90bd91fa6fb09825d1ed8", date: "21 ก.ค. 2569", iso: "2026-07-21", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-0907d72c0c76544d5c0264e2", date: "19 ก.ค. 2569", iso: "2026-07-19", sensor: "Sentinel-2", cloud: 8, coordinates: sentinel2Coordinates },
  { id: "catalog-81532a58d0d6be83bd6ed732", date: "17 ก.ค. 2569", iso: "2026-07-17", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-8e295fc83b2e6b62b3dbbee8", date: "14 ก.ค. 2569", iso: "2026-07-14", sensor: "Sentinel-2", cloud: 67, coordinates: sentinel2Coordinates },
  { id: "catalog-2bab303557a2ce204be1d07a", date: "9 ก.ค. 2569", iso: "2026-07-09", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-779079d7594e6a5afb3b96a8", date: "9 ก.ค. 2569", iso: "2026-07-09", sensor: "Sentinel-2", cloud: 71, coordinates: sentinel2Coordinates },
  { id: "catalog-d54257f5db3c5c55526d8520", date: "4 ก.ค. 2569", iso: "2026-07-04", sensor: "Sentinel-2", cloud: 98, coordinates: sentinel2Coordinates },
  { id: "catalog-71685401b07bd42aad517c48", date: "1 ก.ค. 2569", iso: "2026-07-01", sensor: "Sentinel-2", cloud: 95, coordinates: sentinel2Coordinates },
  { id: "catalog-0540073f14157c7946cc6841", date: "29 มิ.ย. 2569", iso: "2026-06-29", sensor: "Sentinel-2", cloud: 100, coordinates: sentinel2Coordinates },
  { id: "catalog-81f88f944f24c4c6ca7de748", date: "28 มิ.ย. 2569", iso: "2026-06-28", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-e89e5d13f8512bd555f4301f", date: "27 มิ.ย. 2569", iso: "2026-06-27", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-cbe84301af5f33a6cbf8539f", date: "24 มิ.ย. 2569", iso: "2026-06-24", sensor: "Sentinel-2", cloud: 5, coordinates: sentinel2Coordinates },
  { id: "catalog-e8c97a77626802cf731742d8", date: "20 มิ.ย. 2569", iso: "2026-06-20", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-19de555b76482adb5a8c3577", date: "19 มิ.ย. 2569", iso: "2026-06-19", sensor: "Sentinel-2", cloud: 100, coordinates: sentinel2Coordinates },
  { id: "catalog-5ff5b86132953415b4da318a", date: "16 มิ.ย. 2569", iso: "2026-06-16", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-ad4d2d1ed58b5bb2b1d5af08", date: "14 มิ.ย. 2569", iso: "2026-06-14", sensor: "Sentinel-2", cloud: 17, coordinates: sentinel2Coordinates },
  { id: "catalog-ce929279a4ac6a6037419361", date: "11 มิ.ย. 2569", iso: "2026-06-11", sensor: "Sentinel-2", cloud: 65, coordinates: sentinel2Coordinates },
  { id: "catalog-cdac82b94f9bcab33301f7dc", date: "9 มิ.ย. 2569", iso: "2026-06-09", sensor: "Sentinel-2", cloud: 98, coordinates: sentinel2Coordinates },
  { id: "catalog-9fbe50595b167178ca5a71f6", date: "4 มิ.ย. 2569", iso: "2026-06-04", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-391a0aa44eb582eb67f90976", date: "3 มิ.ย. 2569", iso: "2026-06-03", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-5ff19dc89cb966f46447ce33", date: "27 พ.ค. 2569", iso: "2026-05-27", sensor: "Sentinel-1", coordinates: sentinel1Coordinates },
  { id: "catalog-14817ad500100cf5a4363515", date: "25 พ.ค. 2569", iso: "2026-05-25", sensor: "Sentinel-2", cloud: 78, coordinates: sentinel2Coordinates },
];

const plotRing = [
  [100.27361993687678, 14.470451039387699],
  [100.27584606312321, 14.470451039387699],
  [100.27584605591937, 14.469004955303385],
  [100.27361994408062, 14.469004955303385],
  [100.27361993687678, 14.470451039387699],
];

function InteractiveMap({
  sceneId,
  band,
  basemap,
  opacity,
  overlayVisible,
  coordinates,
  className = "",
}: {
  sceneId: string;
  band: string;
  basemap: "satellite" | "streets";
  opacity: number;
  overlayVisible: boolean;
  coordinates: ImageryCoordinates;
  className?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    let cancelled = false;

    import("maplibre-gl").then((maplibreModule) => {
      if (cancelled || !containerRef.current) return;
      const maplibregl: any = maplibreModule.default ?? maplibreModule;
      const imageUrl = new URL(`sentinel-scenes/${sceneId}/${band}.png`, window.location.href).href;
      const map = new maplibregl.Map({
        container: containerRef.current,
        center: [100.274733, 14.469728],
        zoom: 15.5,
        style: {
          version: 8,
          sources: {
            satellite: {
              type: "raster",
              tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
              tileSize: 256,
              attribution: "Tiles © Esri",
            },
            streets: {
              type: "raster",
              tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
              tileSize: 256,
              attribution: "© OpenStreetMap contributors",
            },
          },
          layers: [
            { id: "basemap-satellite", type: "raster", source: "satellite", layout: { visibility: basemap === "satellite" ? "visible" : "none" } },
            { id: "basemap-streets", type: "raster", source: "streets", layout: { visibility: basemap === "streets" ? "visible" : "none" } },
          ],
        },
      });

      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
      map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
      map.on("load", () => {
        map.addSource("sentinel-overlay", {
          type: "image",
          url: imageUrl,
          coordinates,
        });
        map.addLayer({
          id: "sentinel-overlay",
          type: "raster",
          source: "sentinel-overlay",
          layout: { visibility: overlayVisible ? "visible" : "none" },
          paint: { "raster-opacity": opacity },
        });
        map.addSource("demo-plot", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: { name: "DEMO-PLOT-001" },
            geometry: { type: "Polygon", coordinates: [plotRing] },
          },
        });
        map.addLayer({
          id: "demo-plot-fill",
          type: "fill",
          source: "demo-plot",
          paint: { "fill-color": "#20a06b", "fill-opacity": 0.12 },
        });
        map.addLayer({
          id: "demo-plot-line",
          type: "line",
          source: "demo-plot",
          paint: { "line-color": "#ffd34d", "line-width": 4 },
        });
        map.on("click", "demo-plot-fill", (event: any) => {
          new maplibregl.Popup({ offset: 12 })
            .setLngLat(event.lngLat)
            .setHTML("<b>DEMO-PLOT-001</b><br><span>ขอบเขตสาธิต ไม่ใช่แนวเขตที่ดินจริง</span>")
            .addTo(map);
        });
        map.on("mouseenter", "demo-plot-fill", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "demo-plot-fill", () => { map.getCanvas().style.cursor = ""; });
      });
      mapRef.current = map;
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    if (map.getLayer("sentinel-overlay")) map.removeLayer("sentinel-overlay");
    if (map.getSource("sentinel-overlay")) map.removeSource("sentinel-overlay");
    map.addSource("sentinel-overlay", {
      type: "image",
      url: `${new URL(`sentinel-scenes/${sceneId}/${band}.png`, window.location.href).href}?layer=${encodeURIComponent(`${sceneId}-${band}`)}`,
      coordinates,
    });
    map.addLayer({
      id: "sentinel-overlay",
      type: "raster",
      source: "sentinel-overlay",
      layout: { visibility: overlayVisible ? "visible" : "none" },
      paint: { "raster-opacity": opacity },
    }, map.getLayer("demo-plot-fill") ? "demo-plot-fill" : undefined);
  }, [sceneId, band, coordinates]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded()) return;
    if (map.getLayer("basemap-satellite")) map.setLayoutProperty("basemap-satellite", "visibility", basemap === "satellite" ? "visible" : "none");
    if (map.getLayer("basemap-streets")) map.setLayoutProperty("basemap-streets", "visibility", basemap === "streets" ? "visible" : "none");
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.isStyleLoaded() || !map.getLayer("sentinel-overlay")) return;
    map.setLayoutProperty("sentinel-overlay", "visibility", overlayVisible ? "visible" : "none");
    map.setPaintProperty("sentinel-overlay", "raster-opacity", opacity);
  }, [overlayVisible, opacity]);

  return <div ref={containerRef} className={`interactive-map ${className}`} data-testid="interactive-map" aria-label="แผนที่แปลงข้าวแบบซูมและลากได้" />;
}

function Source({ children }: { children: string }) {
  return <span className={`source source-${children.toLowerCase()}`}>{children}</span>;
}

function StateRow({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div className="state-row">
      <span>{label}</span>
      <strong>{value} {source && <Source>{source}</Source>}</strong>
    </div>
  );
}

export default function RiceTwinDashboard() {
  const [view, setView] = useState<View>("overview");
  const [menu, setMenu] = useState(false);
  const [role, setRole] = useState("EXECUTIVE");
  const [sensor, setSensor] = useState<SentinelSensor>("Sentinel-2");
  const [band, setBand] = useState("rice_true_color");
  const [sceneId, setSceneId] = useState("catalog-0907d72c0c76544d5c0264e2");
  const [basemap, setBasemap] = useState<"satellite" | "streets">("satellite");
  const [overlayVisible, setOverlayVisible] = useState(true);
  const [opacity, setOpacity] = useState(0.75);
  const [scenario, setScenario] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const [running, setRunning] = useState(false);
  const [assistant, setAssistant] = useState(false);
  const sensorScenes = sentinelScenes.filter((scene) => scene.sensor === sensor);
  const selectedScene = sentinelScenes.find((scene) => scene.id === sceneId) ?? sensorScenes[0];
  const availableModes = sensor === "Sentinel-2" ? sentinel2Modes : sentinel1Modes;
  const selectedMode = availableModes.find((mode) => mode[0] === band) ?? availableModes[0];

  useEffect(() => {
    if (!running || scenario === null) return;
    const timer = setInterval(() => setTick((value) => Math.min(8, value + 1)), 900);
    return () => clearInterval(timer);
  }, [running, scenario]);

  useEffect(() => {
    if (tick >= 8) setRunning(false);
  }, [tick]);

  const scenarioState = useMemo(() => {
    if (scenario === null) return null;
    const water = scenario === 1
      ? Math.min(8, -12 + tick * 2.7)
      : scenario === 2
        ? -17 - tick * 1.1
        : 4 - tick * 1.9;
    return {
      water: water.toFixed(1),
      progress: Math.round((tick / 8) * 100),
      recommendation:
        scenario === 1
          ? tick < 5 ? "WAIT_12_HOURS" : "PUMP_AVOIDED"
          : scenario === 2 ? "IRRIGATE_NOW" : tick > 5 ? "IRRIGATE" : "MONITOR",
    };
  }, [scenario, tick]);

  const changeView = (next: View) => {
    setView(next);
    setMenu(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const changeSensor = (next: SentinelSensor) => {
    const nextScenes = sentinelScenes.filter((scene) => scene.sensor === next);
    setSensor(next);
    setSceneId(nextScenes[0].id);
    setBand(next === "Sentinel-2" ? sentinel2Modes[0][0] : sentinel1Modes[0][0]);
    setOverlayVisible(true);
  };

  return (
    <div className="site-shell">
      <aside className={`sidebar ${menu ? "sidebar-open" : ""}`}>
        <button className="brand" onClick={() => changeView("overview")}>
          <span className="brand-mark">RT</span>
          <span><b>Rice Twin</b><small>Digital Operations</small></span>
        </button>
        <nav aria-label="เมนูหลัก">
          {nav.map((item) => (
            <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => changeView(item.id)}>
              <i>{item.icon}</i><span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="side-foot">
          <span><i /> Production demo online</span>
          <small>Public edge deployment</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="menu-button" onClick={() => setMenu(!menu)} aria-label="เปิดเมนู">☰</button>
          <div><p>LOW-CARBON RICE DIGITAL TWIN</p><h1>{nav.find((item) => item.id === view)?.label}</h1></div>
          <label>มุมมอง
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {["EXECUTIVE", "FARM MANAGER", "WATER MANAGER", "VERIFIER", "PUBLIC VIEWER"].map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        </header>

        <div className="boundary-warning"><b>DEMO BOUNDARY</b><span>{boundaryWarning}</span></div>

        {view === "overview" && (
          <div className="content">
            <section className="hero">
              <div><p className="kicker">OPERATIONAL OVERVIEW · 24 JUL 2026</p><h2>ตัดสินใจเรื่องน้ำ<br />จากข้อมูลที่ตรวจสอบที่มาได้</h2><p>เชื่อมโยงแปลง เซนเซอร์ ภาพดาวเทียม งานภาคสนาม และความพร้อม MRV ในมุมมองเดียว</p></div>
              <button onClick={() => changeView("scenarios")}>▶ เล่นสถานการณ์สาธิต</button>
            </section>
            <section className="kpi-grid">
              {kpis.map((item) => <article className="kpi-card" key={item.label}><div><span>{item.label}</span><Source>{item.source}</Source></div><strong>{item.value} <small>{item.unit}</small></strong><p>ข้อมูลล่าสุด / รอบ 30 วัน</p></article>)}
            </section>
            <section className="overview-grid">
              <article className="panel map-panel">
                <div className="panel-head"><div><p className="kicker">SPATIAL OPERATIONS</p><h3>แปลงสาธิตและพื้นที่ใกล้เคียง</h3></div><Source>REFERENCE</Source></div>
                <div className="map-wrap">
                  <InteractiveMap sceneId={sceneId} band={band} basemap={basemap} opacity={opacity} overlayVisible={overlayVisible} coordinates={selectedScene.coordinates} />
                  <div className="map-quick-controls">
                    <label>พื้นหลัง
                      <select value={basemap} onChange={(event) => setBasemap(event.target.value as "satellite" | "streets")}>
                        <option value="satellite">ภาพถ่ายดาวเทียม Esri</option>
                        <option value="streets">แผนที่ OpenStreetMap</option>
                      </select>
                    </label>
                    <button onClick={() => changeView("satellite")}>เลือกวันที่ / สีภาพ</button>
                  </div>
                </div>
                <div className="map-legend"><span><i className="legend-main" />DEMO-PLOT-001</span><span>{sensor} · {sensorScenes.length} วัน · ซูม/ลากได้</span><small>ขอบเขตเป็นข้อมูลสังเคราะห์</small></div>
              </article>
              <article className="panel">
                <div className="panel-head"><div><p className="kicker">TWIN STATE</p><h3>สถานะปัจจุบัน</h3></div><Source>DERIVED</Source></div>
                <div className="state-list">
                  <StateRow label="ระยะข้าว" value="แตกกอ · 65 วัน" source="DERIVED" />
                  <StateRow label="สถานะน้ำ" value="DRYING" source="SIMULATED" />
                  <StateRow label="ระดับน้ำ" value="-7.75 cm" source="SIMULATED" />
                  <StateRow label="ความชื้นดิน" value="53.5%" source="SIMULATED" />
                  <StateRow label="ฝนพยากรณ์ 24 ชม." value="22 mm" source="PUBLIC" />
                  <StateRow label="คำแนะนำ" value="WAIT_12_HOURS" source="DERIVED" />
                </div>
                <div className="confidence"><div><span>Data confidence</span><b>91%</b></div><i><em style={{ width: "91%" }} /></i><small>จาก completeness, sensor health, evidence และ spatial consistency</small></div>
              </article>
              <article className="panel water-panel">
                <div className="panel-head"><div><p className="kicker">WATER SIGNAL</p><h3>แนวโน้มระดับน้ำ 30 วัน</h3></div><Source>SIMULATED</Source></div>
                <div className="water-chart">
                  {[62, 55, 49, 42, 36, 31, 25, 63, 57, 50, 44, 37, 31, 26, 68, 60, 53, 46, 39, 33, 27, 65, 58, 51, 45, 39, 33, 28, 66, 54].map((height, index) => <i key={index} style={{ height: `${height}%` }} />)}
                  <span className="threshold">จุดพิจารณาให้น้ำ −15 cm</span>
                </div>
              </article>
              <article className="panel action-panel">
                <div className="panel-head"><div><p className="kicker">ACTION CENTER</p><h3>สิ่งที่ต้องทบทวน</h3></div><span className="count">3</span></div>
                <div className="alert high"><b>Primary sensor discrepancy</b><span>เซนเซอร์สำรองต่างจากค่าหลักเกิน tolerance</span><small>HIGH · 12 นาทีที่แล้ว</small></div>
                <div className="alert"><b>Wait for forecast rainfall</b><span>ทบทวนอีกครั้งใน 12 ชั่วโมงก่อนเดิน pump</span><small>INFO · 20 นาทีที่แล้ว</small></div>
                <div className="alert"><b>Evidence review pending</b><span>ภาพภาคสนาม 1 รายการรอ verifier</span><small>MEDIUM · 1 ชั่วโมงที่แล้ว</small></div>
              </article>
            </section>
          </div>
        )}

        {view === "water" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">TRANSPARENT AWD</p><h2>Water & AWD Decision Support</h2><p>กฎสาธิตที่แสดงอินพุต threshold เหตุผล และข้อจำกัดทุกครั้ง</p></div><span className="status-pill">AWD-DEMO-1.0</span></section>
            <section className="two-col">
              <article className="panel decision">
                <Source>DERIVED</Source><h3>WAIT_12_HOURS</h3><p>ยังไม่ควรเปิดเครื่องสูบน้ำ ให้ตรวจอีกครั้งหลังหน้าต่างพยากรณ์</p>
                <ul><li>ฝนพยากรณ์ 22 มม. สูงกว่า threshold 10 มม.</li><li>ความชื้นดิน 53.5% ยังอยู่ในช่วงยอมรับได้</li><li>ระดับน้ำ −7.75 ซม. ยังไม่ถึง critical threshold −20 ซม.</li></ul>
              </article>
              <article className="panel"><div className="panel-head"><h3>Inputs used</h3><Source>SIMULATED</Source></div><div className="state-list">
                <StateRow label="ระดับน้ำ" value="-7.75 cm" source="SIMULATED" /><StateRow label="ความชื้นดิน" value="53.5%" source="SIMULATED" /><StateRow label="ฝนพยากรณ์" value="22 mm" source="PUBLIC" /><StateRow label="ช่วงแห้ง" value="4 วัน" source="DERIVED" /><StateRow label="Confidence" value="91%" source="DERIVED" />
              </div></article>
            </section>
            <div className="method-note"><b>Decision-support only</b><span>คำแนะนำนี้เป็นตรรกะสาธิต ไม่แทนการอนุมัติของนักวิชาการหรือผู้รับผิดชอบการจัดการน้ำ</span></div>
          </div>
        )}

        {view === "iot" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">DEVICE REGISTRY</p><h2>IoT Operations</h2><p>อุปกรณ์ gateway, battery, signal, protocol และสถานะสอบเทียบ</p></div><span className="status-pill">12 / 12 ONLINE</span></section>
            <section className="device-grid">{devices.map((device) => <article className="device-card" key={device[0]}><div><Source>SIMULATED</Source><span className={`device-status ${device[5] === "WARNING" ? "warning" : ""}`}>{device[5]}</span></div><h3>{device[1]}</h3><p>{device[0]}</p><dl><div><dt>Protocol</dt><dd>{device[2]}</dd></div><div><dt>Battery</dt><dd>{device[3]}</dd></div><div><dt>Signal</dt><dd>{device[4]}</dd></div><div><dt>Last seen</dt><dd>2 min</dd></div></dl></article>)}</section>
          </div>
        )}

        {view === "satellite" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">RICE REMOTE SENSING</p><h2>Sentinel Imagery</h2><p>เลือก Sentinel‑2 แบบสี/ดัชนีพืช หรือ Sentinel‑1 Radar ที่มองผ่านเมฆได้ แล้วเปรียบเทียบแต่ละวันบนแผนที่</p></div><span className="status-pill">22 SCENES · 9 MODES</span></section>
            <section className="satellite-grid">
              <article className="panel satellite-viewer">
                <div className="sensor-tabs" role="group" aria-label="เลือกดาวเทียม">
                  <button className={sensor === "Sentinel-2" ? "active" : ""} aria-pressed={sensor === "Sentinel-2"} onClick={() => changeSensor("Sentinel-2")}><b>Sentinel‑2</b><span>ภาพสี + ดัชนีข้าว · 12 วัน</span></button>
                  <button className={sensor === "Sentinel-1" ? "active" : ""} aria-pressed={sensor === "Sentinel-1"} onClick={() => changeSensor("Sentinel-1")}><b>Sentinel‑1 Radar</b><span>มองผ่านเมฆ · 10 วัน</span></button>
                </div>
                <div className="select-row">
                  <label>วันที่ภาพ
                    <select value={sceneId} onChange={(event) => setSceneId(event.target.value)}>
                      {sensorScenes.map((scene) => <option value={scene.id} key={scene.id}>{scene.date}{scene.sensor === "Sentinel-2" ? ` · เมฆ ${scene.cloud}%` : " · Radar"}</option>)}
                    </select>
                  </label>
                  <label>โหมดสำหรับวิเคราะห์ข้าว
                    <select value={band} onChange={(event) => setBand(event.target.value)}>{availableModes.map((item) => <option value={item[0]} key={item[0]}>{item[1]} · {item[2]}</option>)}</select>
                  </label>
                  <label>พื้นหลังแผนที่
                    <select value={basemap} onChange={(event) => setBasemap(event.target.value as "satellite" | "streets")}><option value="satellite">ภาพถ่ายดาวเทียม Esri</option><option value="streets">OpenStreetMap</option></select>
                  </label>
                </div>
                <div className="imagery-tools">
                  <label><input type="checkbox" checked={overlayVisible} onChange={(event) => setOverlayVisible(event.target.checked)} /> แสดงภาพ {sensor}</label>
                  <label>ความทึบ <input type="range" min="0" max="1" step="0.05" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /><b>{Math.round(opacity * 100)}%</b></label>
                  <span>ใช้ปุ่ม +/− หรือ scroll เพื่อซูม · ลากเพื่อเลื่อนแผนที่</span>
                </div>
                <InteractiveMap key={`${sceneId}-${band}`} sceneId={sceneId} band={band} basemap={basemap} opacity={opacity} overlayVisible={overlayVisible} coordinates={selectedScene.coordinates} className="satellite-map" />
                <div className="satellite-help"><b>{selectedMode[1]}</b><span>{selectedMode[2]} — เป็น analytical indicator ไม่ใช่หลักฐานตรงของ AWD compliance</span></div>
              </article>
              <article className="panel"><div className="panel-head"><h3>Metadata & alignment</h3><Source>PUBLIC</Source></div><div className="state-list"><StateRow label="Acquired" value={selectedScene.iso} /><StateRow label="Sensor" value={sensor === "Sentinel-2" ? "Sentinel-2 L2A" : "Sentinel-1 GRD"} /><StateRow label="Display mode" value={selectedMode[1]} /><StateRow label="Cloud cover" value={sensor === "Sentinel-2" ? `${selectedScene.cloud}%` : "ไม่ใช้กับ Radar"} /><StateRow label="CRS source" value="EPSG:32647" /><StateRow label="Display CRS" value="WGS84 / Web Mercator" /><StateRow label="Plot intersection" value="PASS" source="DERIVED" /></div><div className="satellite-limit">ภาพทั้ง 22 scene ใช้พิกัดที่แปลงจาก GeoTIFF จริงและโหลด layer ใหม่ทุกครั้งที่เปลี่ยนวันหรือโหมด เพื่อไม่ให้ภาพเดิมค้างจาก cache</div></article>
            </section>
          </div>
        )}

        {view === "evidence" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">AUDITABLE EVIDENCE</p><h2>Verifier Portal</h2><p>ทะเบียนหลักฐานพร้อมเวลา แหล่งที่มา hash และผลทบทวน</p></div><span className="status-pill">READINESS 68%</span></section>
            <article className="panel table-panel"><table><thead><tr><th>หลักฐาน</th><th>ประเภท</th><th>วันที่</th><th>ที่มา</th><th>Hash</th><th>ผลทบทวน</th></tr></thead><tbody>
              <tr><td><b>ภาพท่อ AWD รอบที่ 2</b><small>EVID-001</small></td><td>FIELD PHOTO</td><td>22 ก.ค. 2569</td><td><Source>MANUAL</Source></td><td><code>6b86b273ff34…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
              <tr><td><b>Sensor export 30 วัน</b><small>EVID-002</small></td><td>TELEMETRY</td><td>24 ก.ค. 2569</td><td><Source>SIMULATED</Source></td><td><code>d4735e3a265e…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
              <tr><td><b>Sentinel wetness review</b><small>EVID-003</small></td><td>SATELLITE</td><td>19 ก.ค. 2569</td><td><Source>PUBLIC</Source></td><td><code>4e07408562be…</code></td><td><span className="review">PENDING</span></td></tr>
              <tr><td><b>บันทึกการให้น้ำภาคสนาม</b><small>EVID-004</small></td><td>FIELD LOG</td><td>18 ก.ค. 2569</td><td><Source>MANUAL</Source></td><td><code>4b227777d4dd…</code></td><td><span className="review accepted">ACCEPTED</span></td></tr>
            </tbody></table></article>
            <div className="carbon-warning"><div><b>METHODOLOGY NOT CONFIGURED</b><h3>ยังไม่คำนวณหรือกล่าวอ้างคาร์บอนเครดิต</h3></div><p>ยังไม่มี methodology, emission factor หรือ verification ที่อนุมัติ ค่า water saved และ energy avoided เป็น operational estimates ที่ติดป้าย DERIVED เท่านั้น</p></div>
          </div>
        )}

        {view === "scenarios" && (
          <div className="content">
            <section className="section-title"><div><p className="kicker">DETERMINISTIC DEMO ENGINE</p><h2>10 End-to-End Scenarios</h2><p>เลือกสถานการณ์เพื่อเล่นข้อมูล คำแนะนำ alert และ outcome แบบทำซ้ำได้</p></div><Source>SIMULATED</Source></section>
            <section className="scenario-layout">
              <div className="scenario-grid">{scenarios.map((item, index) => <button className={scenario === index ? "selected" : ""} key={item[0]} onClick={() => { setScenario(index); setTick(0); setRunning(true); }}><span>SCENARIO {index + 1}</span><b>{item[0]}</b><small>{item[1]}</small></button>)}</div>
              <aside className="panel scenario-console"><div className="panel-head"><div><p className="kicker">NOW PLAYING</p><h3>{scenario === null ? "เลือกสถานการณ์" : scenarios[scenario][0]}</h3></div><span className="status-pill">{running ? "RUNNING" : tick >= 8 ? "COMPLETED" : "IDLE"}</span></div>
                {scenarioState ? <><div className="scenario-progress"><i style={{ width: `${scenarioState.progress}%` }} /></div><div className="state-list"><StateRow label="Simulation tick" value={`${tick} / 8`} source="SIMULATED" /><StateRow label="ระดับน้ำ" value={`${scenarioState.water} cm`} source="SIMULATED" /><StateRow label="Recommendation" value={scenarioState.recommendation} source="DERIVED" /><StateRow label="Confidence" value={`${Math.max(52, 91 - tick * 2)}%`} source="DERIVED" /></div><div className="scenario-actions"><button onClick={() => setRunning(!running)}>{running ? "Pause" : "Resume"}</button><button onClick={() => { setTick(0); setRunning(false); }}>Reset</button><button className="primary" onClick={() => setTick((value) => Math.min(8, value + 1))}>Next step</button></div></> : <div className="empty">เลือกการ์ดทางซ้ายเพื่อเริ่มเล่น</div>}
              </aside>
            </section>
          </div>
        )}

        <button className="assistant-button" onClick={() => setAssistant(!assistant)} aria-label="เปิดผู้ช่วยอธิบายข้อมูล">AI</button>
        {assistant && <aside className="assistant"><div><p className="kicker">EXPLAINABLE ASSISTANT</p><button onClick={() => setAssistant(false)}>×</button></div><h3>ทำไมยังไม่ควรให้น้ำ?</h3><p>เพราะฝนพยากรณ์ 22 มม. สูงกว่า threshold และความชื้นดินยังยอมรับได้ ระบบจึงแนะนำ <b>WAIT_12_HOURS</b></p><small>ตอบจากกฎ AWD-DEMO-1.0 · ไม่ใช้ external LLM</small></aside>}
      </main>
    </div>
  );
}
