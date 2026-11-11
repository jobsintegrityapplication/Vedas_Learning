# Rigveda Śākala Saṃhitā Corpus Specification

**Status:** target scope approved for planning; source acquisition and full-corpus ingestion are not complete.

## Canonical scope

- **Veda / recension:** Ṛgveda, Śākala Śākhā, Saṃhitā text.
- **Coverage:** all 10 Maṇḍalas, 85 Anuvākas, 1,028 Sūktas and approximately 10,552 mantras (ṛcs), including the 11 Vālakhilya hymns conventionally numbered 8.49–8.59.
- **Count authority:** Vedic Heritage Portal reports 10 Maṇḍalas, 85 Anuvākas, 1,028 Sūktas and 10,552 mantras. Counts are corpus-level expectations, not evidence of imported records. The count is approximate because editions and counting conventions may differ.
- **Excluded:** other Ṛgvedic recensions, Brāhmaṇas, Āraṇyakas, Upaniṣads, translations, and generated/transliterated text unless separately sourced, reviewed and licensed.

## Addressing and content model

Stable address: `RV.<mandala>.<sukta>.<mantra>`; retain source-specific alternate numbering as metadata, never silently normalize it. Store source text, accent/svara marks, pāda boundaries, and editorial punctuation faithfully. Keep Samhitā and Padapāṭha as explicitly distinct text forms. Preserve source spelling and Unicode code points; do not synthesize missing text or accent marks.

Each imported unit must record source/edition, source URL or physical citation, retrieval date, source locator, provenance, rights/license status, reviewer/approval state, text form, and SHA-256 of the exact source artifact. Keep any normalization/transformation as a separately versioned derivative with its own checksum and change log. Missing or disputed units remain missing/quarantined, with a reason; never fill from memory or an unverified secondary source.

### Padapāṭha segmentation

Store the original Saṃhitā form separately from a source-attested Padapāṭha form and ordered token list. Never create Padapāṭha word boundaries by splitting Saṃhitā at ordinary whitespace or by automatic sandhi reversal. Each token may carry a source transcription, transliteration scheme, phonetic features, vowel-length annotations, and Vedic accent annotations; preserve source conventions and provenance for each. Represent sandhi as explicit relationships between Saṃhitā spans and ordered Padapāṭha tokens. If no source Padapāṭha exists, mark segmentation `unavailable`; if evidence is unclear, mark `uncertain`. Either status blocks publication. The current PDFs are not verified Padapāṭha witnesses, so the generated Padapāṭha dataset has 14,260 unavailable profile-variant records and zero publishable rows; it does not synthesize unobserved mantra identities.

## Recitation profiles

The learner may select **Kanchi** or **Sringeri** as separate, named recitation profiles. SaiVeda identifies its supplied PDFs as these two Rigveda recitation styles and says its RCCS presentation encodes sound, melody and rhythm cues. Preserve each labeled source independently; do not assume the supplied files establish institutional endorsement or a universally authoritative lineage. Each profile has independent text/audio provenance and metadata, linked to the same canonical text address. A profile may include tradition/lineage description, performer and teacher attribution, recording provenance, edition/text alignment, recitation form, rights, review status and asset checksum. Specific differences must be transcribed from the source and approved by a qualified reviewer; unknown values stay `unknown`/`not supplied`. Never combine the two recordings or present one as the other's authority. If no reviewed asset exists, show unavailable rather than synthesizing one.

### Documented Shakala count check

The Vedic Heritage Portal's Mandala Krama page provides these per-Maṇḍala counts. The arithmetic sums to 1,028 Sūktas and 10,552 mantras; the portal reports 85 Anuvākas in aggregate. See the [Vedic Heritage Portal Shakala Samhita](https://vedicheritage.gov.in/samhitas/rigveda/shakala-samhita/).

| Maṇḍala | Sūktas | Mantras |
|---:|---:|---:|
| 1 | 191 | 2,006 |
| 2 | 43 | 429 |
| 3 | 62 | 617 |
| 4 | 58 | 589 |
| 5 | 87 | 727 |
| 6 | 75 | 765 |
| 7 | 104 | 841 |
| 8 | 103 | 1,716 |
| 9 | 114 | 1,108 |
| 10 | 191 | 1,754 |
| **Total** | **1,028** | **10,552** |

## Current repository coverage

`content/rigveda_lessons.json` has nine learning excerpts, not a complete sequential corpus. The nine entries and their source document remain under the existing Guru-review requirements. The user has supplied ten Mandala PDF volumes for each of the Kanchi and Sringeri profile labels. A reconciliation pipeline now keeps common reference identities separate from profile variants and compares source coverage against the per-Maṇḍala count table. Its current result is provisional: all 4,130 pages are flagged for OCR, OCR was unavailable, and publication is blocked. It found 6,963 shared provisional addresses, 98 profile-only candidate addresses, and no measurable order conflicts among the shared explicit candidates; it did not adjudicate textual differences. See `content/reconciliation/reconciliation_report.md` and `source_coverage_dashboard.html`. Do not describe the corpus as complete until uncertain extraction, candidate differences, licensing and qualified text review are resolved.

