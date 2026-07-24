import { mkdir, writeFile, access } from "node:fs/promises";

const apiOrigin = process.env.RICE_TWIN_API ?? "http://localhost:8000";
const publicRoot = new URL("../public/", import.meta.url);
const historicalRoot = new URL("historical/", publicRoot);
const sceneRoot = new URL("historical-scenes/", publicRoot);
const plotBase = `${apiOrigin}/api/v1/plots/DEMO-PLOT-001`;

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

async function getData(path) {
  const payload = await getJson(`${plotBase}${path}`);
  return payload.data;
}

async function exists(url) {
  try {
    await access(url);
    return true;
  } catch {
    return false;
  }
}

await mkdir(historicalRoot, { recursive: true });
await mkdir(sceneRoot, { recursive: true });

const [baseline, timelinePayload, cycles, zones, evidence, sensors] = await Promise.all([
  getData("/historical-baseline"),
  getData("/imagery-timeline"),
  getData("/crop-cycles"),
  getData("/recurring-zones"),
  getData("/baseline-evidence"),
  getData("/sensor-location-proposals"),
]);

const timeline = timelinePayload.raw_observations;
const bundle = {
  generated_at: new Date().toISOString(),
  public_static_snapshot: true,
  baseline,
  timeline,
  cycles,
  zones,
  evidence,
  sensors,
};
await writeFile(new URL("data.json", historicalRoot), JSON.stringify(bundle));

const exportFiles = [
  ["timeline.csv", "/exports/timeline.csv"],
  ["historical-baseline.json", "/exports/historical-baseline.json"],
  ["recurring-zones.geojson", "/exports/recurring-zones.geojson"],
  ["sensor-proposals.geojson", "/exports/sensor-proposals.geojson"],
  ["executive-report.html", "/exports/executive-report.html"],
];
await mkdir(new URL("exports/", historicalRoot), { recursive: true });
for (const [filename, path] of exportFiles) {
  const response = await fetch(`${plotBase}${path}`);
  if (!response.ok) throw new Error(`${response.status} ${path}`);
  await writeFile(new URL(`exports/${filename}`, historicalRoot), Buffer.from(await response.arrayBuffer()));
}

const jobs = [];
for (const scene of timeline) {
  const modes = scene.sensor === "Sentinel-2"
    ? ["true_color", "false_color", "ndvi", "evi", "lswi", "ndwi"]
    : ["vv", "vh", "vh_vv_diff"];
  for (const mode of modes) jobs.push({ scene, mode });
}

let cursor = 0;
let completed = 0;
async function worker() {
  while (cursor < jobs.length) {
    const job = jobs[cursor++];
    const directory = new URL(`${job.scene.image_id}/`, sceneRoot);
    const destination = new URL(`${job.mode}.png`, directory);
    await mkdir(directory, { recursive: true });
    if (!(await exists(destination))) {
      const response = await fetch(
        `${apiOrigin}/api/v1/imagery/${job.scene.image_id}/preview.png?mode=${job.mode}`,
      );
      if (!response.ok) throw new Error(`${response.status} ${job.scene.image_id}/${job.mode}`);
      await writeFile(destination, Buffer.from(await response.arrayBuffer()));
    }
    completed++;
    if (completed % 100 === 0 || completed === jobs.length) {
      console.log(`${completed}/${jobs.length} preview assets`);
    }
  }
}

await Promise.all(Array.from({ length: 12 }, () => worker()));
console.log(`Historical static bundle ready: ${timeline.length} scenes, ${jobs.length} previews`);
