CREATE TABLE IF NOT EXISTS rigveda_padapatha (
  record_id CHAR(64) PRIMARY KEY,
  identity_key TEXT NOT NULL,
  profile TEXT NOT NULL CHECK (profile IN ('Kanchi','Sringeri')),
  source_variant_id CHAR(64),
  original_samhita_form TEXT,
  samhita_source_form TEXT,
  padapatha_form TEXT,
  word_order JSONB NOT NULL DEFAULT '[]'::jsonb,
  transliteration TEXT,
  transliteration_scheme TEXT,
  phonetic_features JSONB NOT NULL DEFAULT '[]'::jsonb,
  vowel_length_metadata JSONB NOT NULL DEFAULT '[]'::jsonb,
  vedic_accent_metadata JSONB NOT NULL DEFAULT '[]'::jsonb,
  sandhi_relationships JSONB NOT NULL DEFAULT '[]'::jsonb,
  segmentation_status TEXT NOT NULL CHECK (segmentation_status IN ('source_padapatha_available','uncertain','unavailable')),
  segmentation_method TEXT NOT NULL,
  source_provenance JSONB NOT NULL,
  samhita_provenance JSONB NOT NULL,
  uncertainty_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
  publication_allowed BOOLEAN NOT NULL DEFAULT FALSE,
  reviewer TEXT,
  reviewed_at TIMESTAMPTZ,
  record_checksum CHAR(64) NOT NULL,
  CHECK (NOT publication_allowed OR
    (segmentation_status = 'source_padapatha_available' AND uncertainty_flags = '[]'::jsonb
     AND reviewer IS NOT NULL AND reviewed_at IS NOT NULL))
);