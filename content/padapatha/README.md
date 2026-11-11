# Padapāṭha segmentation data

`padapatha_records.jsonl` and `.csv` contain one tradition-specific record for every provisional Kanchi/Sringeri mantra variant currently available from reconciliation. The supplied PDFs provide Saṃhitā/RCCS candidates, not a verified Padapāṭha witness. Consequently the generated run reports 14,260 records as `unavailable`, with no tokens, inferred splits, or publishable rows. This is not a claim that the complete 10,552-mantra corpus has been enumerated: unobserved identities are not fabricated.

## Source input contract

When an actual Padapāṭha source is obtained, provide JSONL with one row per identity/profile. `identity_key` must match a reconciled address. Use `profile` `Kanchi`, `Sringeri`, or `common`. Keep token order explicitly in the `tokens` array; `word_order` must be contiguous from 1. Each token requires `original_form`; optional `transliteration`, `phonetic_features`, `vowel_length`, and `vedic_accents` must be transcribed or encoded with their own source/reviewer evidence. Do not generate these fields from Saṃhitā text.

Each row must include `source_provenance.source_title`, `source_provenance.source_locator`, and `source_provenance.source_sha256`. Recommended provenance fields include edition, URL, page/folio, publisher, retrieval date, license status, and reviewer. `padapatha_form`, `transliteration`, `transliteration_scheme`, `phonetic_features`, `vowel_length_metadata`, `vedic_accent_metadata`, and `sandhi_relationships` remain separate fields. Sandhi relations should explicitly connect source-backed Saṃhitā spans to Padapāṭha token indices; do not automatically reverse sandhi.

Example shape only (placeholders are not Sanskrit content):

```json
{"identity_key":"RV.01.001.01","profile":"Kanchi","padapatha_form":"<source transcription>","tokens":[{"word_order":1,"original_form":"<source word>","transliteration":"<source transliteration>","phonetic_features":[],"vowel_length":[],"vedic_accents":[]}],"transliteration":"<source transliteration>","transliteration_scheme":"IAST","phonetic_features":[],"vowel_length_metadata":[],"vedic_accent_metadata":[],"sandhi_relationships":[],"review_status":"needs_review","uncertainty_flags":[],"source_provenance":{"source_title":"<edition>","source_locator":"<page/folio>","source_sha256":"<64 hex characters>"}}
```

Run `python scripts/build_padapatha_records.py --padapatha-source <source.jsonl>` after supplying a source witness. The builder never splits by whitespace: it accepts only explicit word-ordered source tokens. Any inherited extraction uncertainty, unreviewed segmentation, or missing source text keeps the record blocked. `padapatha_schema.sql` defines the PostgreSQL table and publication constraint.
