import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render(path = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`https://rice-twin.test${path}`, {
      headers: {
        accept: "text/html",
        "x-forwarded-host": "rice-twin.test",
        "x-forwarded-proto": "https",
      },
    }),
    {
      ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
    },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the Rice Twin command center", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const html = await response.text();
  assert.match(html, /Rice Twin — Low-Carbon Rice Digital Operations/);
  assert.match(html, /Command Center/);
  assert.match(html, /DEMO-PLOT-001 is a synthetic demonstration boundary/);
  assert.match(html, /MRV readiness/);
  assert.match(html, /วัน · ซูม\/ลากได้/);
  assert.match(html, /data-testid="interactive-map"/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/);
});

test("ships production metadata and satellite assets", async () => {
  const response = await render();
  const html = await response.text();
  assert.match(html, /property="og:image" content="https:\/\/rice-twin\.test\/og\.png"/);
  assert.match(html, /name="twitter:card" content="summary_large_image"/);
  assert.match(html, /lang="th"/);
  await Promise.all([
    access(new URL("../public/og.png", import.meta.url)),
    access(new URL("../public/favicon.png", import.meta.url)),
    access(new URL("../public/satellite/ndvi.png", import.meta.url)),
    access(new URL("../public/sentinel-scenes/catalog-0907d72c0c76544d5c0264e2/rice_true_color.png", import.meta.url)),
    access(new URL("../public/sentinel-scenes/catalog-cbe84301af5f33a6cbf8539f/rice_ndvi.png", import.meta.url)),
    access(new URL("../public/sentinel-scenes/catalog-2bb90bd91fa6fb09825d1ed8/rice_sar_vv.png", import.meta.url)),
    access(new URL("../public/sentinel-scenes/catalog-9fbe50595b167178ca5a71f6/rice_sar_diff.png", import.meta.url)),
  ]);
  const packageJson = await readFile(new URL("../package.json", import.meta.url), "utf8");
  const dashboardSource = await readFile(new URL("../app/RiceTwinDashboard.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(packageJson, /maplibre-gl/);
  assert.match(dashboardSource, /Sentinel‑1 Radar/);
  assert.match(dashboardSource, /22 SCENES · 9 MODES/);
  assert.match(dashboardSource, /ตั้งค่าความทึบแบบด่วน/);
  assert.match(dashboardSource, /onInput=/);
  assert.ok(dashboardSource.includes('key={`${sceneId}-${band}`}'));
});

test("ships the historical baseline bundle and both sensor archives", async () => {
  const dashboardSource = await readFile(new URL("../app/RiceTwinDashboard.tsx", import.meta.url), "utf8");
  const historical = JSON.parse(
    await readFile(new URL("../public/historical/data.json", import.meta.url), "utf8"),
  );
  assert.match(dashboardSource, /Historical Baseline Explorer/);
  assert.match(dashboardSource, /ข้อเสนอ · ยังไม่ตรวจยืนยันภาคสนาม/);
  assert.match(dashboardSource, /HISTORICAL REPLAY · เล่นภาพย้อนหลังตามเวลา/);
  assert.match(dashboardSource, /วิธีอ่านกราฟนี้/);
  assert.match(dashboardSource, /ช่องว่างของเส้นหมายถึงไม่มีภาพที่ใช้ได้/);
  assert.match(dashboardSource, /source\.updateImage/);
  assert.match(dashboardSource, /HISTORY_PREFETCH_FRAMES = 8/);
  assert.doesNotMatch(dashboardSource, /key=\{`history-\$\{historyScene\.image_id\}/);
  assert.equal(historical.public_static_snapshot, true);
  assert.equal(historical.timeline.length, 264);
  assert.equal(historical.baseline.usable_image_count, 213);
  assert.ok(historical.cycles.length >= 1);
  assert.equal(historical.evidence.length, 14);
  assert.equal(historical.sensors.length, 8);
  await Promise.all([
    access(new URL("../public/historical-scenes/hist-s2-2025-01-05/ndvi.png", import.meta.url)),
    access(new URL("../public/historical-scenes/hist-s2-2025-01-05/true_color.png", import.meta.url)),
    access(new URL("../public/historical-scenes/hist-s1-2025-01-04/vv.png", import.meta.url)),
    access(new URL("../public/historical-scenes/hist-s1-2025-01-04/vh_vv_diff.png", import.meta.url)),
    access(new URL("../public/historical/exports/recurring-zones.geojson", import.meta.url)),
    access(new URL("../public/historical/exports/executive-report.html", import.meta.url)),
  ]);
});
