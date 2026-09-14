-- Applied on startup. Every statement is idempotent, so this doubles as the
-- migration: adding a column here is safe to ship without a separate tool.

CREATE TABLE IF NOT EXISTS reviews (
    id               UUID PRIMARY KEY,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    label            TEXT         NOT NULL DEFAULT '',
    contract_text    TEXT         NOT NULL,
    model            TEXT         NOT NULL DEFAULT '',

    -- Denormalised summary, so the history list needs no joins.
    clauses_reviewed INTEGER      NOT NULL DEFAULT 0,
    deviations       INTEGER      NOT NULL DEFAULT 0,
    serious          INTEGER      NOT NULL DEFAULT 0,
    minor            INTEGER      NOT NULL DEFAULT 0,
    auto_suggested   INTEGER      NOT NULL DEFAULT 0,
    needs_review     INTEGER      NOT NULL DEFAULT 0,
    uncovered        INTEGER      NOT NULL DEFAULT 0,
    elapsed_seconds  DOUBLE PRECISION NOT NULL DEFAULT 0,

    -- The rules this review was judged against. Without this, editing the
    -- playbook would silently rewrite the meaning of every past review.
    playbook         JSONB        NOT NULL DEFAULT '[]'::jsonb
);

-- REAL is single precision, so a stored 6.13 reads back as 6.130000114440918.
-- Widen it once on databases created before this was noticed.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'reviews'
          AND column_name = 'elapsed_seconds'
          AND data_type = 'real'
    ) THEN
        ALTER TABLE reviews ALTER COLUMN elapsed_seconds TYPE DOUBLE PRECISION;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS findings (
    id                BIGSERIAL PRIMARY KEY,
    review_id         UUID    NOT NULL REFERENCES reviews (id) ON DELETE CASCADE,
    position          INTEGER NOT NULL,          -- preserves the reviewer-facing order

    clause_number     INTEGER NOT NULL,
    clause_heading    TEXT    NOT NULL DEFAULT '',
    rule_id           TEXT,
    rule_title        TEXT,

    verdict           TEXT    NOT NULL,
    tier              TEXT,
    severity          TEXT,
    auto_suggest      BOOLEAN NOT NULL DEFAULT FALSE,
    needs_review      BOOLEAN NOT NULL DEFAULT FALSE,
    source            TEXT,

    original_text     TEXT    NOT NULL DEFAULT '',
    evidence_quote    TEXT    NOT NULL DEFAULT '',
    explanation       TEXT    NOT NULL DEFAULT '',
    proposed_redline  TEXT    NOT NULL DEFAULT '',
    change_summary    TEXT    NOT NULL DEFAULT '',

    redline_addresses JSONB   NOT NULL DEFAULT '[]'::jsonb,
    review_reasons    JSONB   NOT NULL DEFAULT '[]'::jsonb,
    numeric_evidence  JSONB
);

CREATE INDEX IF NOT EXISTS reviews_created_at_idx
    ON reviews (created_at DESC);

CREATE INDEX IF NOT EXISTS findings_review_position_idx
    ON findings (review_id, position);

-- Supports "show me everything a human still needs to look at", across reviews.
CREATE INDEX IF NOT EXISTS findings_needs_review_idx
    ON findings (needs_review)
    WHERE needs_review;

-- Added after reviews already existed; older rows keep an empty playbook.
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS playbook JSONB NOT NULL DEFAULT '[]'::jsonb;
