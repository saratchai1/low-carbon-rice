import { cp, mkdir, readFile, writeFile } from "node:fs/promises";

const pagesOrigin = "https://saratchai1.github.io";
const pagesBase = "/low-carbon-rice/";
const output = new URL("../pages-dist/", import.meta.url);
const workerUrl = new URL("../dist/server/index.js", import.meta.url);
workerUrl.searchParams.set("export", `${Date.now()}`);
const { default: worker } = await import(workerUrl.href);

const response = await worker.fetch(
  new Request(`${pagesOrigin}/`, {
    headers: {
      accept: "text/html",
      "x-forwarded-host": "saratchai1.github.io",
      "x-forwarded-proto": "https",
    },
  }),
  {
    ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) },
  },
  { waitUntil() {}, passThroughOnException() {} },
);

if (!response.ok) throw new Error(`Static render failed: ${response.status}`);

let html = await response.text();
html = html
  .replaceAll('href="/assets/', 'href="./assets/')
  .replaceAll('href="/favicon.png"', 'href="./favicon.png"')
  .replaceAll('src="/assets/', 'src="./assets/')
  .replaceAll('import("/assets/', 'import("./assets/')
  .replaceAll(`${pagesOrigin}/og.png`, `${pagesOrigin}${pagesBase}og.png`)
  .replaceAll('content="/og.png"', `content="${pagesOrigin}${pagesBase}og.png"`);

await mkdir(output, { recursive: true });
await cp(new URL("../dist/client/", import.meta.url), output, { recursive: true, force: true });
await writeFile(new URL("index.html", output), html);
await writeFile(new URL(".nojekyll", output), "");

const exported = await readFile(new URL("index.html", output), "utf8");
if (!exported.includes("Rice Twin — Low-Carbon Rice Digital Operations")) {
  throw new Error("Exported page is missing the production title");
}
if (exported.includes('href="/assets/') || exported.includes('import("/assets/')) {
  throw new Error("Exported page still contains root-relative build assets");
}

console.log(new URL("../pages-dist/", import.meta.url).pathname);
