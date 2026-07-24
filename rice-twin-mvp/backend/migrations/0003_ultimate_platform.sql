CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(80) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE plots ADD COLUMN IF NOT EXISTS project_id VARCHAR(64);
ALTER TABLE plots ADD COLUMN IF NOT EXISTS farmer_id VARCHAR(64);
CREATE INDEX IF NOT EXISTS ix_plots_project_id ON plots(project_id);
CREATE INDEX IF NOT EXISTS ix_plots_farmer_id ON plots(farmer_id);

ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS crop_year INTEGER;
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS rice_variety VARCHAR(120);
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS planting_method VARCHAR(80);
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS planting_date DATE;
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS expected_harvest_date DATE;
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS actual_harvest_date DATE;
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS baseline_scenario TEXT;
ALTER TABLE crop_seasons ADD COLUMN IF NOT EXISTS project_scenario TEXT;

CREATE INDEX IF NOT EXISTS ix_sensor_observations_plot_metric_time
    ON sensor_observations(plot_id, metric, observed_at DESC);
CREATE INDEX IF NOT EXISTS ix_twin_state_plot_created
    ON twin_state_snapshots(plot_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_alerts_status_severity
    ON alerts(status, severity, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_evidence_plot_review
    ON evidence_records(plot_id, review_status);

INSERT INTO schema_migrations(version)
VALUES ('0003_ultimate_platform')
ON CONFLICT (version) DO NOTHING;
