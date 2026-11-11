-- Staging schema: common identity is separate from Kanchi/Sringeri text variants.
-- Records are not publishable until uncertainty flags are cleared and a qualified reviewer approves.
CREATE TABLE IF NOT EXISTS rigveda_mantra_identity (
    identity_key TEXT PRIMARY KEY CHECK (identity_key ~ '^RV\.[0-9]{2}\.[0-9]{3}\.[0-9]{2,3}$'),
    mandala SMALLINT NOT NULL CHECK (mandala BETWEEN 1 AND 10),
    sukta SMALLINT NOT NULL CHECK (sukta > 0),
    mantra SMALLINT NOT NULL CHECK (mantra > 0),
    source_presence JSONB NOT NULL,
    occurrences_by_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
    identity_status TEXT NOT NULL DEFAULT 'provisional_extraction',
    uncertainty_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    publication_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT publication_allowed OR
      (identity_status = 'approved' AND uncertainty_flags = '[]'::jsonb AND reviewer IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS rigveda_tradition_variant (
    variant_id CHAR(64) PRIMARY KEY,
    identity_key TEXT NOT NULL REFERENCES rigveda_mantra_identity(identity_key),
    profile TEXT NOT NULL CHECK (profile IN ('Kanchi','Sringeri')),
    source_pdf TEXT NOT NULL,
    source_url TEXT,
    source_sha256 CHAR(64) NOT NULL,
    source_page INTEGER NOT NULL CHECK (source_page > 0),
    license_status TEXT NOT NULL DEFAULT 'unknown',
    source_text_segment TEXT NOT NULL,
    devanagari_candidate TEXT NOT NULL,
    rccs_candidate TEXT NOT NULL,
    iast_candidate TEXT NOT NULL,
    svara_marks JSONB NOT NULL DEFAULT '[]'::jsonb,
    rccs_visual_cues_location JSONB NOT NULL,
    extraction_method TEXT NOT NULL,
    extraction_confidence NUMERIC(5,4) NOT NULL,
    uncertainty_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    variant_relation TEXT NOT NULL DEFAULT 'undetermined'
      CHECK (variant_relation IN ('undetermined','same_text','legitimate_profile_difference','textual_discrepancy')),
    text_comparison_status TEXT NOT NULL DEFAULT 'blocked_uncertain_extraction',
    publication_blockers JSONB NOT NULL DEFAULT '[]'::jsonb,
    publication_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    reviewer TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (NOT publication_allowed OR
      (extraction_confidence >= 0.98 AND uncertainty_flags = '[]'::jsonb AND reviewer IS NOT NULL AND reviewed_at IS NOT NULL AND license_status = 'cleared')),
    FOREIGN KEY (profile, source_sha256, source_page)
      REFERENCES rigveda_pdf_page_staging(profile, source_sha256, source_page)
);

CREATE INDEX IF NOT EXISTS ix_rigveda_variant_identity_profile ON rigveda_tradition_variant(identity_key, profile);
CREATE INDEX IF NOT EXISTS ix_rigveda_variant_source ON rigveda_tradition_variant(source_sha256, source_page);
