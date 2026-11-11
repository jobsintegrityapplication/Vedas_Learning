#!/usr/bin/env python3
"""Reconcile Kanchi and Sringeri source candidates without publishing uncertain text.

Reads content/ingestion/mantra_candidates.jsonl and manifest.json, then writes
separate identity/variant datasets, reconciliation reports, a static dashboard,
and PostgreSQL staging DDL. Comparisons remain provisional whenever extraction
or reference identity is uncertain.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "content" / "ingestion"
DEFAULT_OUTPUT = ROOT / "content" / "reconciliation"
EXPECTED = {
    1: {"suktas": 191, "mantras": 2006},
    2: {"suktas": 43, "mantras": 429},
    3: {"suktas": 62, "mantras": 617},
    4: {"suktas": 58, "mantras": 589},
    5: {"suktas": 87, "mantras": 727},
    6: {"suktas": 75, "mantras": 765},
    7: {"suktas": 104, "mantras": 841},
    8: {"suktas": 103, "mantras": 1716},
    9: {"suktas": 114, "mantras": 1108},
    10: {"suktas": 191, "mantras": 1754},
}
EXPECTED_TOTALS = {"mandalas": 10, "anuvakas": 85, "suktas": 1028, "mantras": 10552}
PROFILE_NAMES = ("Kanchi", "Sringeri")
IDENTITY_CSV_FIELDS = ["identity_key", "mandala", "sukta", "mantra", "profile_presence_json",
                       "occurrences_by_profile_json", "identity_status", "uncertainty_flags_json", "publication_allowed"]
VARIANT_CSV_FIELDS = ["variant_id", "identity_key", "profile", "source_pdf", "source_url", "source_sha256",
                      "source_page", "license_status", "source_text_segment", "devanagari_candidate",
                      "rccs_candidate", "iast_candidate", "svara_marks_json", "rccs_visual_cues_location_json",
                      "extraction_method", "extraction_confidence", "uncertainty_flags_json", "variant_relation",
                      "text_comparison_status", "publication_blockers_json", "publication_allowed"]
REFERENCE = re.compile(r"^RV\.(\d{2})\.(\d{3})\.(\d{2,3})$")
PUBLICATION_BLOCKERS = {
    "text_layer_unreliable_ocr_needed", "ocr_engine_or_required_language_data_unavailable",
    "broken_font_mapping_cid_placeholders", "low_ocr_confidence", "ocr_output_unreviewed",
    "sukta_reference_ambiguous_or_missing", "mantra_marker_not_detected",
}


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity_parts(ref: str) -> tuple[int, int, int] | None:
    match = REFERENCE.fullmatch(ref or "")
    if not match:
        return None
    return tuple(map(int, match.groups()))  # type: ignore[return-value]


def is_publishable_candidate(row: dict[str, Any]) -> bool:
    flags = set(row.get("uncertainty_flags") or [])
    return (
        not flags.intersection(PUBLICATION_BLOCKERS)
        and row.get("confidence", 0) >= 0.98
        and row.get("review_status") in {"guru_approved", "approved"}
    )


def inversion_count(values: list[int]) -> int:
    """Count order inversions in O(n log n) without materializing all pairs."""
    if not values:
        return 0
    tree = [0] * (len(values) + 2)

    def add(index: int) -> None:
        index += 1
        while index < len(tree):
            tree[index] += 1
            index += index & -index

    def prefix(index: int) -> int:
        total = 0
        index += 1
        while index > 0:
            total += tree[index]
            index -= index & -index
        return total

    result = 0
    for seen, value in enumerate(values):
        result += seen - prefix(value)
        add(value)
    return result


def build_dashboard(report: dict[str, Any], out: Path) -> None:
    rows = []
    for item in report["mandala_coverage"]:
        rows.append(
            "<tr>"
            f"<td>{item['mandala']:02d}</td><td>{item['expected_suktas']}</td><td>{item['expected_mantras']}</td>"
            f"<td>{item['Kanchi']['candidate_rows']}</td><td>{item['Kanchi']['unique_address_candidates']}</td>"
            f"<td>{item['Kanchi']['ambiguous_or_unassigned']}</td>"
            f"<td>{item['Sringeri']['candidate_rows']}</td><td>{item['Sringeri']['unique_address_candidates']}</td>"
            f"<td>{item['Sringeri']['ambiguous_or_unassigned']}</td><td>{html.escape(item['status'])}</td></tr>"
        )
    totals = report["summary"]
    html_doc = f'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rigveda Profile Reconciliation</title>
<style>
body{{font:15px/1.45 system-ui,Segoe UI,Arial,sans-serif;margin:0;background:#f4f6f8;color:#18212b}}
main{{max-width:1500px;margin:auto;padding:28px}}h1{{margin:0 0 8px}}.warning{{background:#fff2cc;border-left:5px solid #d49a00;padding:14px 18px;margin:18px 0}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:18px 0}}
.card{{background:white;border:1px solid #dbe1e7;border-radius:8px;padding:14px}}.card b{{display:block;font-size:24px}}
.tablewrap{{overflow:auto;background:#fff;border:1px solid #dbe1e7;border-radius:8px}}
table{{border-collapse:collapse;width:100%;min-width:1050px}}th,td{{padding:9px 11px;text-align:right;border-bottom:1px solid #e6eaee;white-space:nowrap}}
th{{background:#eaf0f5;position:sticky;top:0}}td:first-child,th:first-child,td:last-child,th:last-child{{text-align:left}}
.note{{color:#52606d}}code{{background:#eaf0f5;padding:2px 4px;border-radius:3px}}
</style><main>
<h1>Rigveda Śākala: Kanchi / Sringeri source coverage</h1>
<p class="note">Generated {html.escape(report['generated_at'])}. Counts below are extraction candidates, not approved corpus counts.</p>
<div class="warning"><b>Publication blocked.</b> OCR was unavailable and all 4,130 source pages are flagged for uncertain extraction. No extracted text is publishable. Identity matches, missing entries, order changes, and text variants remain provisional until OCR and review.</div>
<section class="cards">
<div class="card"><span>Expected structure</span><b>10 / 85 / 1,028 / 10,552</b><small>Mandalas / Anuvakas / Suktas / mantras</small></div>
<div class="card"><span>Source PDFs</span><b>{totals['source_pdf_count']}</b><small>10 per profile</small></div>
<div class="card"><span>Page records</span><b>{totals['page_records']:,}</b><small>All pages marked OCR-needed</small></div>
<div class="card"><span>Provisional shared identities</span><b>{totals['provisional_common_identities']:,}</b><small>Reference-only; unverified</small></div>
<div class="card"><span>Unmatched candidate identities</span><b>{totals['provisional_profile_only_identities']:,}</b><small>May reflect extraction errors</small></div>
<div class="card"><span>Publishable variants</span><b>0</b><small>All blocked by uncertainty</small></div>
</section>
<h2>Coverage by Maṇḍala</h2>
<div class="tablewrap"><table><thead><tr><th>Maṇḍala</th><th>Expected Sūktas</th><th>Expected mantras</th><th>Kanchi candidate rows</th><th>Kanchi unique addresses</th><th>Kanchi unresolved</th><th>Sringeri candidate rows</th><th>Sringeri unique addresses</th><th>Sringeri unresolved</th><th>Status</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<h2>Reconciliation status</h2><p>Reference overlap: {totals['provisional_common_identities']:,} candidates. Apparent profile-only references: {totals['provisional_profile_only_identities']:,}. Duplicate identity groups: {totals['duplicate_identity_groups']:,}. Provisional order conflicts: {totals['provisional_order_conflicts']:,}. Confirmed textual differences: {totals['confirmed_textual_differences']} (text comparison blocked for uncertain records).</p>
<p class="note">Expected counts come from the Vedic Heritage Portal Śākala Samhitā table. See <code>reconciliation_report.md</code> and <code>reconciliation_report.json</code> for method, caveats, reference lists, and source links.</p>
</main></html>'''
    (out / "source_coverage_dashboard.html").write_text(html_doc, encoding="utf-8")


SCHEMA_SQL = r'''-- Staging schema: common identity is separate from Kanchi/Sringeri text variants.
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
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if sum(x["suktas"] for x in EXPECTED.values()) != EXPECTED_TOTALS["suktas"]:
        raise SystemExit("Expected sukta inventory does not sum to documented total")
    if sum(x["mantras"] for x in EXPECTED.values()) != EXPECTED_TOTALS["mantras"]:
        raise SystemExit("Expected mantra inventory does not sum to documented total")

    source_manifest = json.loads((args.input / "manifest.json").read_text(encoding="utf-8"))
    source_by_hash = {s["sha256"]: s for s in source_manifest.get("sources", [])}
    by_profile: dict[str, list[dict[str, Any]]] = {p: [] for p in PROFILE_NAMES}
    with (args.input / "mantra_candidates.jsonl").open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("profile") in by_profile:
                by_profile[row["profile"]].append(row)

    addressed: dict[str, dict[str, list[dict[str, Any]]]] = {p: defaultdict(list) for p in PROFILE_NAMES}
    unresolved: list[dict[str, Any]] = []
    row_by_id: dict[str, dict[str, Any]] = {}
    profile_metrics: dict[str, dict[int, dict[str, Any]]] = {
        p: {m: {"candidate_rows": 0, "explicit_number_candidates": 0, "ambiguous_or_unassigned": 0,
                "unique_address_candidates": 0, "observed_suktas": set(), "duplicates": 0}
            for m in EXPECTED}
        for p in PROFILE_NAMES
    }
    for profile, rows in by_profile.items():
        for seq, row in enumerate(rows):
            parts = identity_parts(row.get("reference_candidate"))
            mandala = int(row.get("mandala") or (parts[0] if parts else 0))
            if mandala in profile_metrics[profile]:
                metric = profile_metrics[profile][mandala]
                metric["candidate_rows"] += 1
                metric["explicit_number_candidates"] += row.get("mantra_number_candidate") is not None
                metric["ambiguous_or_unassigned"] += parts is None
            if parts:
                addressed[profile][row["reference_candidate"]].append(row)
                row_by_id[f"{profile}:{seq}"] = row
            else:
                unresolved.append({"profile": profile, "candidate_sequence": seq, **row,
                                   "publication_allowed": False,
                                   "publication_blockers": ["no_confident_mandala_sukta_mantra_identity", "uncertain_extraction"]})
            for sukta_ref in row.get("sukta_reference_candidates") or []:
                sm = re.fullmatch(r"RV\.(\d{2})\.(\d{3})", sukta_ref or "")
                if sm:
                    smandala, sukta = map(int, sm.groups())
                    if smandala in profile_metrics[profile]:
                        profile_metrics[profile][smandala]["observed_suktas"].add(sukta)

    address_sets = {p: set(addressed[p]) for p in PROFILE_NAMES}
    common = address_sets["Kanchi"] & address_sets["Sringeri"]
    kanchi_only = address_sets["Kanchi"] - address_sets["Sringeri"]
    sringeri_only = address_sets["Sringeri"] - address_sets["Kanchi"]
    duplicate_groups: list[dict[str, Any]] = []
    duplicate_rows_by_profile = Counter()
    for profile in PROFILE_NAMES:
        for ref, occurrences in addressed[profile].items():
            parts = identity_parts(ref)
            if parts and parts[0] in profile_metrics[profile]:
                profile_metrics[profile][parts[0]]["unique_address_candidates"] += 1
            if len(occurrences) > 1:
                duplicate_rows_by_profile[profile] += len(occurrences) - 1
                duplicate_groups.append({
                    "profile": profile, "identity_key": ref, "occurrence_count": len(occurrences),
                    "source_pages": sorted({x["source_page"] for x in occurrences}),
                    "status": "provisional_duplicate_uncertain_extraction",
                    "publication_allowed": False,
                })
    for profile in PROFILE_NAMES:
        for mandala in EXPECTED:
            metric = profile_metrics[profile][mandala]
            metric["duplicates"] = duplicate_rows_by_profile[profile]

    def sequence(profile: str) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for row in by_profile[profile]:
            ref = row.get("reference_candidate")
            if ref and ref in address_sets[profile] and ref not in seen:
                seen.add(ref)
                ordered.append(ref)
        return ordered

    seq_k = [x for x in sequence("Kanchi") if x in common]
    seq_s = [x for x in sequence("Sringeri") if x in common]
    rank_k = {x: i for i, x in enumerate(seq_k)}
    rank_s = {x: i for i, x in enumerate(seq_s)}
    order_changed = [x for x in common if rank_k.get(x) != rank_s.get(x)]
    inversions = inversion_count([rank_s[x] for x in seq_k if x in rank_s])
    order_conflicts = [
        {"identity_key": ref, "kanchi_rank": rank_k.get(ref), "sringeri_rank": rank_s.get(ref),
         "status": "provisional_order_difference_uncertain_extraction", "publication_allowed": False}
        for ref in sorted(order_changed, key=lambda x: rank_k.get(x, 10**12))
    ]

    identity_rows: list[dict[str, Any]] = []
    for ref in sorted(address_sets["Kanchi"] | address_sets["Sringeri"]):
        parts = identity_parts(ref)
        assert parts
        present = [p for p in PROFILE_NAMES if ref in address_sets[p]]
        identity_rows.append({
            "identity_key": ref, "mandala": parts[0], "sukta": parts[1], "mantra": parts[2],
            "profile_presence": present,
            "occurrences_by_profile": {p: len(addressed[p].get(ref, [])) for p in PROFILE_NAMES},
            "identity_status": "provisional_extraction_candidate",
            "uncertainty_flags": ["reference_derived_from_uncertain_pdf_text_layer"],
            "publication_allowed": False,
        })

    variant_rows: list[dict[str, Any]] = []
    text_queue: list[dict[str, Any]] = []
    variant_ids_by_ref: dict[str, dict[str, list[str]]] = defaultdict(lambda: {p: [] for p in PROFILE_NAMES})
    for identity in identity_rows:
        ref = identity["identity_key"]
        for profile in PROFILE_NAMES:
            for ordinal, row in enumerate(addressed[profile].get(ref, [])):
                source = source_by_hash.get(row.get("source_sha256"), {})
                flags = sorted(set(row.get("uncertainty_flags") or []))
                blockers = sorted(set(flags) & PUBLICATION_BLOCKERS)
                if not is_publishable_candidate(row):
                    blockers = sorted(set(blockers) | {"qualified_review_not_recorded"})
                license_status = source.get("license_status", "unknown")
                if "no reuse license identified" in license_status.lower():
                    blockers = sorted(set(blockers) | {"rights_status_unresolved"})
                variant_id = hashlib.sha256(
                    f"{profile}|{row.get('source_sha256')}|{row.get('source_page')}|{ref}|{ordinal}".encode("utf-8")
                ).hexdigest()
                variant_rows.append({
                    "variant_id": variant_id, "identity_key": ref, "profile": profile,
                    "source_pdf": row.get("source_pdf"), "source_url": source.get("source_url"),
                    "source_sha256": row.get("source_sha256"), "source_page": row.get("source_page"),
                    "license_status": license_status,
                    "rccs_visual_cues_location": {"dataset": "../ingestion/pages.jsonl", "profile": profile,
                                                    "source_sha256": row.get("source_sha256"), "source_page": row.get("source_page")},
                    "source_text_segment": row.get("source_text_segment", ""),
                    "devanagari_candidate": row.get("devanagari_candidate", ""),
                    "rccs_candidate": row.get("rccs_text_candidate", ""),
                    "iast_candidate": row.get("romanized_sanskrit_iast_candidate", ""),
                    "svara_marks": row.get("svara_marks", []),
                    "extraction_method": row.get("extraction_method"),
                    "extraction_confidence": row.get("confidence", 0),
                    "uncertainty_flags": flags,
                    "variant_relation": "undetermined",
                    "text_comparison_status": "blocked_uncertain_extraction",
                    "publication_blockers": blockers,
                    "publication_allowed": False,
                })
                variant_ids_by_ref[ref][profile].append(variant_id)
        if ref in common:
            text_queue.append({
                "identity_key": ref,
                "kanchi_variant_ids": variant_ids_by_ref[ref]["Kanchi"],
                "sringeri_variant_ids": variant_ids_by_ref[ref]["Sringeri"],
                "text_comparison_status": "blocked_uncertain_extraction",
                "textual_difference_classification": "not_adjudicated",
                "publication_allowed": False,
            })

    profile_only = [
        {"identity_key": ref, "present_in": "Kanchi", "missing_from_candidate_set": "Sringeri",
         "status": "provisional_missing_uncertain_extraction", "occurrences": len(addressed["Kanchi"][ref]),
         "publication_allowed": False}
        for ref in sorted(kanchi_only)
    ] + [
        {"identity_key": ref, "present_in": "Sringeri", "missing_from_candidate_set": "Kanchi",
         "status": "provisional_missing_uncertain_extraction", "occurrences": len(addressed["Sringeri"][ref]),
         "publication_allowed": False}
        for ref in sorted(sringeri_only)
    ]

    mandala_coverage = []
    for mandala, expected in EXPECTED.items():
        item: dict[str, Any] = {"mandala": mandala, "expected_suktas": expected["suktas"],
                                "expected_mantras": expected["mantras"]}
        for profile in PROFILE_NAMES:
            rows = [r for r in by_profile[profile] if int(r.get("mandala") or 0) == mandala]
            refs_for_mandala = {x for x in address_sets[profile] if identity_parts(x)[0] == mandala}
            metric = profile_metrics[profile][mandala]
            item[profile] = {
                "candidate_rows": len(rows),
                "explicit_number_candidates": metric["explicit_number_candidates"],
                "unique_address_candidates": len(refs_for_mandala),
                "candidate_suktas_seen": len(metric["observed_suktas"]),
                "expected_suktas_missing_from_candidate_labels": max(0, expected["suktas"] - len(metric["observed_suktas"])),
                "ambiguous_or_unassigned": metric["ambiguous_or_unassigned"],
                "extraction_uncertain_pages": len({r["source_page"] for r in rows if PUBLICATION_BLOCKERS.intersection(r.get("uncertainty_flags") or [])}),
            }
        item["status"] = "not_validated_uncertain_extraction"
        mandala_coverage.append(item)

    source_counts = Counter(s.get("profile") for s in source_manifest.get("sources", []))
    page_validation = source_manifest.get("validation", {})
    observed_marker_counts = page_validation.get("explicit_mantra_number_candidates_by_profile", {})
    total_structure_valid = (
        sum(x["suktas"] for x in EXPECTED.values()) == EXPECTED_TOTALS["suktas"]
        and sum(x["mantras"] for x in EXPECTED.values()) == EXPECTED_TOTALS["mantras"]
        and len(EXPECTED) == EXPECTED_TOTALS["mandalas"]
    )
    all_uncertain = page_validation.get("pages_ocr_unavailable") == page_validation.get("page_records")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "source_structure": {
            "recension": "Rigveda Shakala Samhita",
            "expected_totals": EXPECTED_TOTALS,
            "expected_by_mandala": {str(k): v for k, v in EXPECTED.items()},
            "expected_totals_sum_check": "passed" if total_structure_valid else "failed",
            "authority_url": "https://vedicheritage.gov.in/samhitas/rigveda/shakala-samhita/",
            "accessed_date": "2026-11-07",
            "definition_note": "Includes the portal's Mandala VIII total as published; numbering/count conventions must remain edition-specific.",
        },
        "source_files": {"pdf_count": len(source_manifest.get("sources", [])), "pdfs_by_profile": dict(source_counts),
                         "pages": page_validation.get("page_records"), "ocr_required_pages": page_validation.get("pages_with_ocr_needed"),
                         "ocr_unavailable_pages": page_validation.get("pages_ocr_unavailable"),
                         "inventory": [{"profile": s.get("profile"), "mandala": s.get("mandala"),
                                        "source_url": s.get("source_url"), "source_sha256": s.get("sha256"),
                                        "page_count": s.get("page_count"), "edition": s.get("edition"),
                                        "license_status": s.get("license_status")} for s in source_manifest.get("sources", [])]},
        "structure_comparison": {
            "per_mandala_expected_counts_arithmetic": "passed" if total_structure_valid else "failed",
            "expected_anukavas": EXPECTED_TOTALS["anuvakas"],
            "anuvaka_coverage_status": "not_extracted",
            "explicit_marker_candidates_by_profile": observed_marker_counts,
            "candidate_count_delta_from_10552": {p: int(observed_marker_counts.get(p, 0)) - EXPECTED_TOTALS["mantras"] for p in PROFILE_NAMES},
            "coverage_validation_status": "blocked_uncertain_extraction",
        },
        "summary": {
            "source_pdf_count": len(source_manifest.get("sources", [])),
            "page_records": page_validation.get("page_records", 0),
            "provisional_common_identities": len(common),
            "provisional_profile_only_identities": len(profile_only),
            "duplicate_identity_groups": len(duplicate_groups),
            "provisional_order_conflicts": len(order_changed),
            "kendall_order_inversions_on_common_candidates": inversions,
            "text_comparisons_blocked": len(text_queue),
            "confirmed_textual_differences": 0,
            "text_difference_status": "not_evaluated_due_uncertain_extraction",
            "publishable_records": 0 if all_uncertain else "review_required",
            "publication_gate": "blocked_uncertain_extraction" if all_uncertain else "review_required",
        },
        "profile_candidate_summary": {
            p: {
                "candidate_rows": len(by_profile[p]),
                "unique_explicit_identity_candidates": len(address_sets[p]),
                "duplicate_address_groups": sum(len(v) > 1 for v in addressed[p].values()),
                "duplicate_extra_rows": sum(max(0, len(v) - 1) for v in addressed[p].values()),
                "unassigned_candidates": sum(not r.get("reference_candidate") for r in by_profile[p]),
                "all_candidates_uncertain": all(not is_publishable_candidate(r) for r in by_profile[p]),
            } for p in PROFILE_NAMES
        },
        "mandala_coverage": mandala_coverage,
        "apparent_missing_candidate_files": ["profile_only_candidates.jsonl"],
        "duplicate_candidate_file": "duplicate_identity_candidates.jsonl",
        "order_conflict_file": "order_conflicts.jsonl",
        "text_comparison_queue_file": "text_comparison_queue.jsonl",
        "identity_file": "mantra_identities.jsonl",
        "variant_file": "tradition_variants.jsonl",
        "unresolved_file": "unresolved_candidates.jsonl",
        "limitations": [
            "All 4,130 pages are flagged for unreliable text extraction and OCR was unavailable; reference labels are provisional.",
            "Apparent missing/duplicate/reordered counts are candidate-set comparisons, not verified textual findings.",
            "Textual equality/difference was not classified. Every common-reference comparison is blocked until clean OCR and review.",
            "The source structure supplies per-Mandala totals but not a fully reviewed mantra-count inventory for each Sukta; no absent mantra IDs are synthesized.",
            "Profile-specific text, RCCS/svara cues, and source provenance remain in separate variant rows. No variant is overwritten or merged.",
            "The PDF source license is not established; check the source manifest before reuse or publication.",
        ],
    }

    write_jsonl(args.out / "mantra_identities.jsonl", identity_rows)
    write_jsonl(args.out / "tradition_variants.jsonl", variant_rows)
    write_jsonl(args.out / "unresolved_candidates.jsonl", unresolved)
    write_jsonl(args.out / "profile_only_candidates.jsonl", profile_only)
    write_jsonl(args.out / "duplicate_identity_candidates.jsonl", duplicate_groups)
    write_jsonl(args.out / "order_conflicts.jsonl", order_conflicts)
    write_jsonl(args.out / "text_comparison_queue.jsonl", text_queue)
    with (args.out / "mantra_identities.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=IDENTITY_CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in identity_rows:
            writer.writerow({
                "identity_key": row["identity_key"], "mandala": row["mandala"], "sukta": row["sukta"], "mantra": row["mantra"],
                "profile_presence_json": json.dumps(row["profile_presence"], ensure_ascii=False),
                "occurrences_by_profile_json": json.dumps(row["occurrences_by_profile"], ensure_ascii=False),
                "identity_status": row["identity_status"],
                "uncertainty_flags_json": json.dumps(row["uncertainty_flags"], ensure_ascii=False),
                "publication_allowed": str(row["publication_allowed"]).lower(),
            })
    with (args.out / "tradition_variants.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=VARIANT_CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in variant_rows:
            writer.writerow({
                "variant_id": row["variant_id"], "identity_key": row["identity_key"], "profile": row["profile"],
                "source_pdf": row["source_pdf"], "source_url": row["source_url"], "source_sha256": row["source_sha256"],
                "source_page": row["source_page"], "license_status": row["license_status"],
                "source_text_segment": row["source_text_segment"], "devanagari_candidate": row["devanagari_candidate"],
                "rccs_candidate": row["rccs_candidate"], "iast_candidate": row["iast_candidate"],
                "svara_marks_json": json.dumps(row["svara_marks"], ensure_ascii=False),
                "rccs_visual_cues_location_json": json.dumps(row["rccs_visual_cues_location"], ensure_ascii=False),
                "extraction_method": row["extraction_method"], "extraction_confidence": row["extraction_confidence"],
                "uncertainty_flags_json": json.dumps(row["uncertainty_flags"], ensure_ascii=False),
                "variant_relation": row["variant_relation"], "text_comparison_status": row["text_comparison_status"],
                "publication_blockers_json": json.dumps(row["publication_blockers"], ensure_ascii=False),
                "publication_allowed": str(row["publication_allowed"]).lower(),
            })
    (args.out / "reconciliation_schema.sql").write_text(SCHEMA_SQL, encoding="utf-8")
    import_sql = r'''-- Run after ../ingestion/postgres_import.sql loads rigveda_pdf_page_staging.
-- Run from content/reconciliation. Imported rows remain blocked from publication.
\copy rigveda_mantra_identity(identity_key,mandala,sukta,mantra,source_presence,occurrences_by_profile,identity_status,uncertainty_flags,publication_allowed) FROM 'mantra_identities.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
\copy rigveda_tradition_variant(variant_id,identity_key,profile,source_pdf,source_url,source_sha256,source_page,license_status,source_text_segment,devanagari_candidate,rccs_candidate,iast_candidate,svara_marks,rccs_visual_cues_location,extraction_method,extraction_confidence,uncertainty_flags,variant_relation,text_comparison_status,publication_blockers,publication_allowed) FROM 'tradition_variants.csv' WITH (FORMAT csv, HEADER true, ENCODING 'UTF8');
'''
    (args.out / "reconciliation_import.sql").write_text(import_sql, encoding="utf-8")
    (args.out / "reconciliation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "shakala_structure.json").write_text(json.dumps(report["source_structure"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    md = [
        "# Kanchi–Sringeri Rigveda Śākala Reconciliation",
        "",
        f"**Generated:** {report['generated_at']}  ",
        "**Decision:** publication blocked because extraction is uncertain.  ",
        "**Source authority:** [Vedic Heritage Portal Śākala Samhitā](https://vedicheritage.gov.in/samhitas/rigveda/shakala-samhita/)",
        "",
        "> The prior ingestion flagged every page for OCR. OCR was unavailable. This is a reconciliation of extracted reference candidates only; it does not establish textual variants, omissions, or a complete corpus.",
        "",
        "## Summary",
        "",
        f"- Source PDFs: {report['summary']['source_pdf_count']} ({source_counts.get('Kanchi',0)} Kanchi, {source_counts.get('Sringeri',0)} Sringeri).",
        f"- Page records: {report['summary']['page_records']:,}; OCR-unavailable pages: {report['source_files']['ocr_unavailable_pages']:,}.",
        f"- Provisional common identity candidates: {len(common):,}.",
        f"- Apparent profile-only candidates: {len(profile_only):,} (not verified missing mantras).",
        f"- Duplicate address groups: {len(duplicate_groups):,}.",
        f"- Provisional order conflicts: {len(order_changed):,}; relative-order inversion count: {inversions:,}.",
        f"- Text comparisons blocked: {len(text_queue):,}; confirmed textual differences: 0 (not evaluated).",
        "- Publishable records: **0**.",
        "",
        "## Documented Śākala structure and extracted candidates",
        "",
        "Expected per-Maṇḍala counts are from the linked Vedic Heritage Portal. Candidate values count extracted markers/addresses, not approved records.",
        "",
        "| Maṇḍala | Expected Sūktas | Expected mantras | Kanchi address candidates | Kanchi unresolved | Sringeri address candidates | Sringeri unresolved |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for m in mandala_coverage:
        md.append(f"| {m['mandala']:02d} | {m['expected_suktas']} | {m['expected_mantras']} | {m['Kanchi']['unique_address_candidates']} | {m['Kanchi']['ambiguous_or_unassigned']} | {m['Sringeri']['unique_address_candidates']} | {m['Sringeri']['ambiguous_or_unassigned']} |")
    md += [
        f"| **Total** | **{EXPECTED_TOTALS['suktas']}** | **{EXPECTED_TOTALS['mantras']}** | **{sum(m['Kanchi']['unique_address_candidates'] for m in mandala_coverage)}** | — | **{sum(m['Sringeri']['unique_address_candidates'] for m in mandala_coverage)}** | — |",
        "",
        "Structure arithmetic: the per-Maṇḍala table sums to 1,028 Sūktas and 10,552 mantras, matching the documented totals. The extract does not validate those totals because all pages remain uncertain and the source table does not enumerate every mantra count by Sukta.",
        "",
        "## Difference detection policy",
        "",
        "- **Missing:** `profile_only_candidates.jsonl` lists explicit addresses seen in one extracted candidate set only. Treat each as a review lead, not a confirmed omission.",
        "- **Duplicates:** `duplicate_identity_candidates.jsonl` records repeated addresses by profile and source page; no occurrence is selected or discarded.",
        "- **Reordered:** `order_conflicts.jsonl` compares first-seen page order over common explicit addresses. The result is provisional because extraction/reference assignment is uncertain.",
        "- **Textually different:** no difference is adjudicated. `text_comparison_queue.jsonl` lists common identities and blocks comparison until OCR/review. Preserve Kanchi and Sringeri strings in separate variant records.",
        "- **Publication:** every identity and variant currently has `publication_allowed=false`; schema constraints require clean extraction and review before enabling publication.",
        "",
        "## Files",
        "",
        "- `mantra_identities.jsonl`: one common provisional identity per explicit reference.",
        "- `tradition_variants.jsonl`: source-specific Kanchi/Sringeri candidates linked to identity; text remains separate.",
        "- `mantra_identities.csv` and `tradition_variants.csv`: separate PostgreSQL staging imports.",
        "- `unresolved_candidates.jsonl`: candidates without a confident Mandala.Sukta.Mantra address.",
        "- `reconciliation_schema.sql`: PostgreSQL identity/variant tables with publication gate.",
        "- `reconciliation_import.sql`: psql imports; load the source-page staging table first.",
        "- `source_coverage_dashboard.html`: static per-Maṇḍala source-coverage view.",
        "",
    ]
    (args.out / "reconciliation_report.md").write_text("\n".join(md), encoding="utf-8")
    build_dashboard(report, args.out)

    outputs = sorted(p for p in args.out.iterdir() if p.is_file())
    report["output_checksums"] = [{"file": p.name, "sha256": file_sha256(p), "size_bytes": p.stat().st_size}
                                  for p in outputs if p.name != "reconciliation_report.json"]
    (args.out / "reconciliation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "profile_candidate_summary": report["profile_candidate_summary"],
                      "output_directory": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
