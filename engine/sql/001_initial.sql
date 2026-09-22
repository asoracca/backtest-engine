CREATE TABLE runs (
    run_id TEXT PRIMARY KEY CHECK(length(run_id) = 64),
    data_hash TEXT NOT NULL CHECK(length(data_hash) = 64),
    config_hash TEXT NOT NULL CHECK(length(config_hash) = 64),
    comparison_key TEXT NOT NULL,
    sensitivity_key TEXT NOT NULL,
    slippage_bps REAL NOT NULL CHECK(slippage_bps >= 0),
    metadata TEXT NOT NULL CHECK(json_valid(metadata)),
    inputs TEXT NOT NULL CHECK(json_valid(inputs)),
    manifest_hash TEXT NOT NULL CHECK(length(manifest_hash) = 64)
);
CREATE INDEX runs_comparison ON runs(comparison_key, run_id);
CREATE INDEX runs_sensitivity ON runs(sensitivity_key, slippage_bps);
CREATE TABLE events (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL CHECK(sequence >= 0),
    kind TEXT NOT NULL CHECK(kind IN ('SIGNAL','ORDER_ACCEPTED','ORDER_REJECTED','FILL_BOOKED','VALUATION')),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(run_id, sequence),
    CHECK(kind = json_extract(payload, '$.type'))
);
CREATE INDEX events_kind ON events(run_id, kind, sequence);
CREATE TABLE ledgers (
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    ledger TEXT NOT NULL CHECK(ledger IN ('orders','fills','trades','positions','cash','equity','rejections')),
    row_number INTEGER NOT NULL CHECK(row_number >= 0),
    dt TEXT NOT NULL,
    equity REAL,
    cash REAL CHECK(cash >= -0.00000001),
    commission REAL CHECK(commission >= 0),
    slippage_cost REAL CHECK(slippage_cost >= 0),
    payload TEXT NOT NULL CHECK(json_valid(payload)),
    PRIMARY KEY(run_id, ledger, row_number),
    CHECK(ledger != 'cash' OR (equity IS NOT NULL AND cash IS NOT NULL)),
    CHECK(ledger != 'fills' OR (commission IS NOT NULL AND slippage_cost IS NOT NULL)),
    CHECK(equity IS json_extract(payload, '$.equity')),
    CHECK(cash IS json_extract(payload, '$.cash')),
    CHECK(commission IS json_extract(payload, '$.commission')),
    CHECK(slippage_cost IS json_extract(payload, '$.slippage_cost')),
    CHECK(dt = COALESCE(json_extract(payload, '$.dt'), json_extract(payload, '$.fill_dt'),
                        json_extract(payload, '$.submitted_dt')))
);
CREATE INDEX ledgers_timeline ON ledgers(run_id, ledger, dt);
