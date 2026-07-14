CREATE TABLE IF NOT EXISTS gift_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gift_entries (
    id TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL CHECK(entry_type IN ('candidate', 'given', 'received')),
    title TEXT NOT NULL,
    giver TEXT,
    recipient TEXT,
    gift_date TEXT,
    amount_yen INTEGER CHECK(amount_yen IS NULL OR amount_yen >= 0),
    memo TEXT,
    related_event TEXT,
    occasion_date TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gift_entries_date
    ON gift_entries(gift_date, created_at);
CREATE INDEX IF NOT EXISTS idx_gift_entries_people
    ON gift_entries(giver, recipient);
