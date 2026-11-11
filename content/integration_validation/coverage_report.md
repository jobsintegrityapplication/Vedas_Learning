# Corpus and integration coverage report

**Status: not_production_ready**

## Source files

- PDF count: 20 (Kanchi 10, Sringeri 10)
- SHA-256 matches: 20/20
- All Maṇḍalas represented once per profile: True

## Corpus and extraction

- Documented structure: 10 Maṇḍalas, 1,028 Sūktas, 10,552 mantras; arithmetic matches the declared table.
- Ingestion: 21,191 heuristic candidates, 7,061 provisional identity rows, 14,260 tradition-specific candidate variants.
- UTF-8 candidate texts: 21,191; with Devanāgarī: 21,129; still showing broken `(cid:…)` glyph mappings: 21,131.
- Padapāṭha records: 14,260; status counts: `{'unavailable': 14260}`; rows with word tokens: 0; publishable: 0.
- Candidate address counts are not a verified coverage count and must not be used to claim corpus completeness.

## Integration checks

- Identity rows remain separate from Kanchi/Sringeri variants; profile keys are valid and no variant references a missing identity: True
- Every profile/Maṇḍala has at least one provisional reference candidate: True
- Non-fixture source audio files: 0
- Validated profile audio: 0; all absent assets must remain unavailable.
- Production Sanskrit ASR/forced alignment/pronunciation/svara provider: none; evaluation confidence and feature recognition were not testable.

## Production-readiness blockers

- All 4,130 pages need OCR/text review; OCR tooling/data was unavailable in the ingestion run.
- Candidate references are heuristic and do not establish all 10,552 canonical mantra identities.
- No verified source Padapāṭha segmentation exists; word order cannot be tested for unavailable rows.
- No validated Kanchi/Sringeri reference audio assets are present.
- No production Sanskrit speech, forced-alignment, phonetic, or Vedic svara engine is configured; confidence-based evaluation cannot be validated.
- Rights/license and edition identification remain unresolved for the source PDFs.
