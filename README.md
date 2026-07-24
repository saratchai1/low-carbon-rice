# Rice Twin Public

Production-hosted public demonstration of the Ultimate Low-Carbon Rice Digital
Twin. This edge-compatible edition presents the executive command center,
transparent AWD logic, twelve simulated IoT devices, Sentinel-2 rice display
modes, verifier evidence and ten deterministic scenarios without depending on
the local Docker/PostGIS runtime.

All operational values are explicitly labelled as `SIMULATED`, `PUBLIC`,
`MANUAL`, `DERIVED` or `REFERENCE`.

> DEMO-PLOT-001 is a synthetic demonstration boundary. It is not a cadastral,
> surveyed, legal, ownership, or officially verified plot boundary.

The public demo does not calculate or claim carbon credits. Its MRV surfaces
show readiness and limitations only.

## Local development

```bash
npm install
npm run dev
```

## Validation

```bash
npm run build
node --test tests/rendered-html.test.mjs
```
