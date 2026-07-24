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
  assert.match(html, /Sentinel‑2 · 12 วัน · ซูม\/ลากได้/);
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
  ]);
  const packageJson = await readFile(new URL("../package.json", import.meta.url), "utf8");
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
  assert.match(packageJson, /maplibre-gl/);
});
