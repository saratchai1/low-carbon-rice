import { readFile, writeFile } from "node:fs/promises";

const source = process.env.RICE_TWIN_HISTORICAL_SUMMARY
  ? new URL(`file://${process.env.RICE_TWIN_HISTORICAL_SUMMARY}`)
  : new URL("../../../output_3yr_4per_month/summary_3yr_4per_month.csv", import.meta.url);
const destination = new URL("../public/historical/cloud-cover.json", import.meta.url);
const rows = (await readFile(source, "utf8")).trim().split(/\r?\n/);
const header = rows.shift()?.split(",") ?? [];
const dateIndex = header.indexOf("date");
const sensorIndex = header.indexOf("satellite");
const cloudIndex = header.indexOf("cloud_cover_%");

if ([dateIndex, sensorIndex, cloudIndex].some((index) => index < 0)) {
  throw new Error("Historical summary is missing date, satellite, or cloud_cover_%");
}

const scenes = {};
for (const row of rows) {
  const columns = row.split(",");
  if (columns[sensorIndex] !== "Sentinel-2") continue;
  const cloudCover = Number(columns[cloudIndex]);
  if (!Number.isFinite(cloudCover)) continue;
  scenes[`hist-s2-${columns[dateIndex]}`] = Number(cloudCover.toFixed(3));
}

await writeFile(destination, `${JSON.stringify({
  source: "Sentinel-2 STAC eo:cloud_cover",
  threshold_percent: 20,
  scene_count: Object.keys(scenes).length,
  scenes,
}, null, 2)}\n`);

console.log(`${Object.keys(scenes).length} Sentinel-2 cloud-cover records`);
