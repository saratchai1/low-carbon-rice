CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(80) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tables are declared in app.models and created idempotently by SQLAlchemy
-- before file migrations run.  The indexes below are kept in SQL so an
-- existing installation receives the same query plan as a fresh database.
CREATE INDEX IF NOT EXISTS ix_imagery_assets_plot_acquired
    ON imagery_assets(plot_id, acquisition_datetime);
CREATE INDEX IF NOT EXISTS ix_imagery_assets_status
    ON imagery_assets(processing_status);
CREATE INDEX IF NOT EXISTS ix_imagery_plot_metrics_plot_acquired
    ON imagery_plot_metrics(plot_id, acquisition_datetime);
CREATE INDEX IF NOT EXISTS ix_historical_crop_seasons_plot_start
    ON historical_crop_seasons(plot_id, probable_start_date);
CREATE INDEX IF NOT EXISTS ix_recurring_zones_plot_type
    ON recurring_zones(plot_id, zone_type);
CREATE INDEX IF NOT EXISTS ix_baseline_evidence_plot_claim
    ON baseline_evidence_items(plot_id, claim_key);
CREATE INDEX IF NOT EXISTS ix_sensor_location_proposals_plot_type
    ON sensor_location_proposals(plot_id, sensor_type);
CREATE INDEX IF NOT EXISTS ix_temporal_analysis_runs_plot_period
    ON temporal_analysis_runs(plot_id, period_start, period_end);

INSERT INTO schema_migrations(version)
VALUES ('0004_historical_imagery')
ON CONFLICT (version) DO NOTHING;
