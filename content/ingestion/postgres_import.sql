-- PostgreSQL staging import for pages.csv. Run from the ingestion output folder.
-- Keep the source-page candidate text immutable; do not promote to canonical lessons
-- until a reviewer approves the unit against an identified edition.
CREATE TABLE IF NOT EXISTS rigveda_pdf_page_staging (
    id BIGSERIAL PRIMARY KEY,
    profile TEXT NOT NULL CHECK (profile IN ('Kanchi', 'Sringeri')),
    mandala SMALLINT NOT NULL CHECK (mandala BETWEEN 1 AND 10),
    source_pdf TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    source_page INTEGER NOT NULL CHECK (source_page > 0),
    unit_kind TEXT NOT NULL,
    sukta_references JSONB NOT NULL DEFAULT '[]'::jsonb,
    mantra_reference_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    devanagari_text TEXT NOT NULL,
    rccs_text_candidate TEXT NOT NULL,
    romanized_sanskrit_iast_candidate TEXT NOT NULL,
    transliteration_candidate TEXT NOT NULL,
    svara_marks JSONB NOT NULL DEFAULT '[]'::jsonb,
    rccs_visual_cues JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_method TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL,
    ocr_confidence NUMERIC(5,4),
    review_status TEXT NOT NULL,
    uncertainty_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (profile, source_sha256, source_page)
);

-- CSV uses UTF-8 with BOM for spreadsheet compatibility. PostgreSQL accepts UTF-8;
-- use HEADER and CSV quote semantics. Run psql with client_encoding=UTF8.
\copy rigveda_pdf_page_staging(profile,mandala,source_pdf,source_sha256,source_page,unit_kind,sukta_references,mantra_reference_candidates,raw_text,normalized_text,devanagari_text,rccs_text_candidate,romanized_sanskrit_iast_candidate,transliteration_candidate,svara_marks,rccs_visual_cues,extraction_method,confidence,ocr_confidence,review_status,uncertainty_flags) FROM 'pages.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');

CREATE TABLE IF NOT EXISTS rigveda_pdf_mantra_candidate_staging (
    id BIGSERIAL PRIMARY KEY,
    profile TEXT NOT NULL CHECK (profile IN ('Kanchi', 'Sringeri')),
    mandala SMALLINT NOT NULL CHECK (mandala BETWEEN 1 AND 10),
    source_pdf TEXT NOT NULL,
    source_sha256 CHAR(64) NOT NULL,
    source_page INTEGER NOT NULL CHECK (source_page > 0),
    reference_candidate TEXT,
    sukta_reference_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
    mantra_number_candidate INTEGER,
    verse_marker_evidence TEXT,
    source_text_segment TEXT NOT NULL,
    devanagari_candidate TEXT NOT NULL,
    rccs_text_candidate TEXT NOT NULL,
    romanized_sanskrit_iast_candidate TEXT NOT NULL,
    transliteration_candidate TEXT NOT NULL,
    svara_marks JSONB NOT NULL DEFAULT '[]'::jsonb,
    extraction_method TEXT NOT NULL,
    segmentation_method TEXT NOT NULL,
    confidence NUMERIC(5,4) NOT NULL,
    ocr_confidence NUMERIC(5,4),
    review_status TEXT NOT NULL,
    uncertainty_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
\copy rigveda_pdf_mantra_candidate_staging(profile,mandala,source_pdf,source_sha256,source_page,reference_candidate,sukta_reference_candidates,mantra_number_candidate,verse_marker_evidence,source_text_segment,devanagari_candidate,rccs_text_candidate,romanized_sanskrit_iast_candidate,transliteration_candidate,svara_marks,extraction_method,segmentation_method,confidence,ocr_confidence,review_status,uncertainty_flags) FROM 'mantra_candidates.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
