# Kanchi–Sringeri Rigveda Śākala Reconciliation

**Generated:** 2026-11-06T20:16:03.377993+00:00  
**Decision:** publication blocked because extraction is uncertain.  
**Source authority:** [Vedic Heritage Portal Śākala Samhitā](https://vedicheritage.gov.in/samhitas/rigveda/shakala-samhita/)

> The prior ingestion flagged every page for OCR. OCR was unavailable. This is a reconciliation of extracted reference candidates only; it does not establish textual variants, omissions, or a complete corpus.

## Summary

- Source PDFs: 20 (10 Kanchi, 10 Sringeri).
- Page records: 4,130; OCR-unavailable pages: 4,130.
- Provisional common identity candidates: 6,963.
- Apparent profile-only candidates: 98 (not verified missing mantras).
- Duplicate address groups: 233.
- Provisional order conflicts: 0; relative-order inversion count: 0.
- Text comparisons blocked: 6,963; confirmed textual differences: 0 (not evaluated).
- Publishable records: **0**.

## Documented Śākala structure and extracted candidates

Expected per-Maṇḍala counts are from the linked Vedic Heritage Portal. Candidate values count extracted markers/addresses, not approved records.

| Maṇḍala | Expected Sūktas | Expected mantras | Kanchi address candidates | Kanchi unresolved | Sringeri address candidates | Sringeri unresolved |
|---:|---:|---:|---:|---:|---:|---:|
| 01 | 191 | 2006 | 595 | 1349 | 584 | 1424 |
| 02 | 43 | 429 | 258 | 170 | 258 | 170 |
| 03 | 62 | 617 | 262 | 328 | 251 | 366 |
| 04 | 58 | 589 | 306 | 267 | 280 | 313 |
| 05 | 87 | 727 | 723 | 2 | 725 | 2 |
| 06 | 75 | 765 | 764 | 5 | 764 | 8 |
| 07 | 104 | 841 | 836 | 3 | 837 | 5 |
| 08 | 103 | 1716 | 1713 | 1 | 1714 | 1 |
| 09 | 114 | 1108 | 1106 | 1 | 1107 | 0 |
| 10 | 191 | 1754 | 486 | 1209 | 455 | 1307 |
| **Total** | **1028** | **10552** | **7049** | — | **6975** | — |

Structure arithmetic: the per-Maṇḍala table sums to 1,028 Sūktas and 10,552 mantras, matching the documented totals. The extract does not validate those totals because all pages remain uncertain and the source table does not enumerate every mantra count by Sukta.

## Difference detection policy

- **Missing:** `profile_only_candidates.jsonl` lists explicit addresses seen in one extracted candidate set only. Treat each as a review lead, not a confirmed omission.
- **Duplicates:** `duplicate_identity_candidates.jsonl` records repeated addresses by profile and source page; no occurrence is selected or discarded.
- **Reordered:** `order_conflicts.jsonl` compares first-seen page order over common explicit addresses. The result is provisional because extraction/reference assignment is uncertain.
- **Textually different:** no difference is adjudicated. `text_comparison_queue.jsonl` lists common identities and blocks comparison until OCR/review. Preserve Kanchi and Sringeri strings in separate variant records.
- **Publication:** every identity and variant currently has `publication_allowed=false`; schema constraints require clean extraction and review before enabling publication.

## Files

- `mantra_identities.jsonl`: one common provisional identity per explicit reference.
- `tradition_variants.jsonl`: source-specific Kanchi/Sringeri candidates linked to identity; text remains separate.
- `mantra_identities.csv` and `tradition_variants.csv`: separate PostgreSQL staging imports.
- `unresolved_candidates.jsonl`: candidates without a confident Mandala.Sukta.Mantra address.
- `reconciliation_schema.sql`: PostgreSQL identity/variant tables with publication gate.
- `reconciliation_import.sql`: psql imports; load the source-page staging table first.
- `source_coverage_dashboard.html`: static per-Maṇḍala source-coverage view.
