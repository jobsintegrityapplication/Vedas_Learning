#!/usr/bin/env python3
"""Audit source artifacts and corpus/integration readiness without publishing content."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
OUT = CONTENT / "integration_validation"
MANIFEST = CONTENT / "ingestion" / "manifest.json"
EXPECTED = {
    1: (191, 2006), 2: (43, 429), 3: (62, 617), 4: (58, 589), 5: (87, 727),
    6: (75, 765), 7: (104, 841), 8: (103, 1716), 9: (114, 1108), 10: (191, 1754),
}
DEV = re.compile(r"[\u0900-\u097f\ua8e0-\ua8ff]")
CID = re.compile(r"\(cid:\d+\)")
REF = re.compile(r"^RV\.(\d{2})\.(\d{3})\.(\d{2,3})$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def jsonl(path: Path):
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except Exception as exc:
                    raise RuntimeError(f"Invalid UTF-8 JSONL at {path}:{line_number}: {exc}") from exc


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sources = manifest.get("sources", [])
    source_checks = []
    source_mandala_profile = Counter()
    for source in sources:
        path = Path(source["file"])
        exists = path.is_file()
        observed_hash = sha256(path) if exists else None
        valid = exists and observed_hash == source.get("sha256")
        source_checks.append({"profile": source.get("profile"), "mandala": source.get("mandala"),
                              "path": str(path), "exists": exists, "manifest_sha256": source.get("sha256"),
                              "observed_sha256": observed_hash, "checksum_match": valid})
        if valid:
            source_mandala_profile[(source.get("profile"), int(source.get("mandala")))] += 1

    validation = json.loads((CONTENT / "ingestion" / "validation.json").read_text(encoding="utf-8"))
    candidate_profiles = Counter()
    candidate_ref_counts = Counter()
    candidate_unique_refs: dict[str, set[str]] = defaultdict(set)
    candidate_refs_by_mandala: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    unicode_records = 0
    cid_records = 0
    devanagari_records = 0
    candidate_count = 0
    for row in jsonl(CONTENT / "ingestion" / "mantra_candidates.jsonl"):
        candidate_count += 1
        profile = row.get("profile", "unknown")
        candidate_profiles[profile] += 1
        text = row.get("source_text_segment") or ""
        if text:
            unicode_records += 1
        if DEV.search(text):
            devanagari_records += 1
        if CID.search(text):
            cid_records += 1
        ref = row.get("reference_candidate")
        match = REF.fullmatch(ref or "")
        if match and int(match.group(2)) > 0:
            candidate_ref_counts[profile] += 1
            candidate_unique_refs[profile].add(ref)
            candidate_refs_by_mandala[profile][str(int(match.group(1)))].add(ref)

    identities = list(jsonl(CONTENT / "reconciliation" / "mantra_identities.jsonl"))
    variants = list(jsonl(CONTENT / "reconciliation" / "tradition_variants.jsonl"))
    identity_keys = {row["identity_key"] for row in identities}
    profile_variant_counts = Counter(row.get("profile") for row in variants)
    dangling_variants = [row.get("variant_id") for row in variants if row.get("identity_key") not in identity_keys]
    bad_profile_rows = [row.get("variant_id") for row in variants if row.get("profile") not in {"Kanchi", "Sringeri"}]

    pad_report = json.loads((CONTENT / "padapatha" / "padapatha_report.json").read_text(encoding="utf-8"))
    pad_counts = Counter()
    pad_rows = 0
    fabricated_tokens = 0
    bad_word_order = 0
    for row in jsonl(CONTENT / "padapatha" / "padapatha_records.jsonl"):
        pad_rows += 1
        pad_counts[row.get("segmentation_status", "missing")] += 1
        words = row.get("word_order") or []
        if words:
            fabricated_tokens += 1
            if any(item.get("word_order") != index for index, item in enumerate(words, 1)):
                bad_word_order += 1

    recon = json.loads((CONTENT / "reconciliation" / "reconciliation_report.json").read_text(encoding="utf-8"))
    sums = {"mandalas": 10, "suktas": sum(v[0] for v in EXPECTED.values()),
            "mantras": sum(v[1] for v in EXPECTED.values())}
    audio_files = []
    for path in CONTENT.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus"}:
            if "fixture" not in str(path).lower() and "test" not in str(path).lower():
                audio_files.append(str(path.relative_to(ROOT)))

    source_ok = len(sources) == 20 and all(x["checksum_match"] for x in source_checks)
    structure_ok = sums == {"mandalas": 10, "suktas": 1028, "mantras": 10552}
    identity_separation_ok = not dangling_variants and not bad_profile_rows and set(profile_variant_counts) <= {"Kanchi", "Sringeri"}
    all_profile_mandalas = all(source_mandala_profile[(profile, mandala)] == 1
                               for profile in ("Kanchi", "Sringeri") for mandala in range(1, 11))
    report = {
        "audit_status": "not_production_ready",
        "source_files": {"count": len(sources), "count_by_profile": dict(Counter(x.get("profile") for x in sources)),
                         "sha256_match_count": sum(x["checksum_match"] for x in source_checks),
                         "all_10_mandalas_in_both_profiles": all_profile_mandalas, "details": source_checks},
        "documented_structure": {"counts": sums, "matches_documented_total": structure_ok,
                                  "per_mandala": {str(k): {"suktas": v[0], "mantras": v[1]} for k, v in EXPECTED.items()}},
        "ingestion": {"page_records": validation.get("page_records"), "candidate_records": candidate_count,
                      "candidate_counts_by_profile": dict(candidate_profiles),
                      "resolved_reference_candidates_by_profile": {p: len(candidate_unique_refs[p]) for p in ("Kanchi", "Sringeri")},
                      "resolved_references_by_profile_mandala": {p: {m: len(refs) for m, refs in sorted(candidate_refs_by_mandala[p].items())} for p in ("Kanchi", "Sringeri")},
                      "representative_provisional_references": {p: {m: sorted(refs)[0] for m, refs in sorted(candidate_refs_by_mandala[p].items()) if refs} for p in ("Kanchi", "Sringeri")},
                      "resolved_candidate_rows_by_profile": dict(candidate_ref_counts),
                      "candidate_text_records_with_unicode": unicode_records,
                      "candidate_text_records_with_devanagari": devanagari_records,
                      "candidate_text_records_with_broken_cid_placeholders": cid_records,
                      "ocr_available": manifest.get("ocr_available"),
                      "pages_marked_uncertain": validation.get("pages_with_ocr_needed")},
        "reconciliation": {"summary": recon.get("summary"), "identity_rows": len(identities),
                           "variant_rows": len(variants), "variant_counts_by_profile": dict(profile_variant_counts),
                           "variants_with_missing_identity": len(dangling_variants), "invalid_profile_variants": len(bad_profile_rows),
                           "identity_and_variant_profiles_separate": identity_separation_ok},
        "padapatha": {"record_count": pad_rows, "reported_count": pad_report.get("record_count"),
                      "status_counts": dict(pad_counts), "reported_status_counts": pad_report.get("status_counts"),
                      "rows_with_word_tokens": fabricated_tokens, "bad_word_order_rows": bad_word_order,
                      "publishable_count": pad_report.get("publishable_count", 0)},
        "audio_and_evaluation": {"local_nonfixture_audio_files": audio_files,
                                 "validated_profile_audio_count": 0,
                                 "production_sanskrit_asr_configured": False,
                                 "forced_alignment_provider_configured": False,
                                 "pronunciation_feature_provider_configured": False,
                                 "vedic_svara_provider_configured": False,
                                 "evaluation_confidence_available": False,
                                 "profile_audio_missing_is_reported_unavailable": True},
        "coverage_gaps": [
            "All 4,130 pages need OCR/text review; OCR tooling/data was unavailable in the ingestion run.",
            "Candidate references are heuristic and do not establish all 10,552 canonical mantra identities.",
            "No verified source Padapāṭha segmentation exists; word order cannot be tested for unavailable rows.",
            "No validated Kanchi/Sringeri reference audio assets are present.",
            "No production Sanskrit speech, forced-alignment, phonetic, or Vedic svara engine is configured; confidence-based evaluation cannot be validated.",
            "Rights/license and edition identification remain unresolved for the source PDFs.",
        ],
    }
    (OUT / "coverage_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = ["# Corpus and integration coverage report", "", f"**Status: {report['audit_status']}**", "",
          "## Source files", "", f"- PDF count: {len(sources)} (Kanchi {report['source_files']['count_by_profile'].get('Kanchi', 0)}, Sringeri {report['source_files']['count_by_profile'].get('Sringeri', 0)})",
          f"- SHA-256 matches: {report['source_files']['sha256_match_count']}/20",
          f"- All Maṇḍalas represented once per profile: {all_profile_mandalas}", "",
          "## Corpus and extraction", "", "- Documented structure: 10 Maṇḍalas, 1,028 Sūktas, 10,552 mantras; arithmetic matches the declared table.",
          f"- Ingestion: {candidate_count:,} heuristic candidates, {len(identities):,} provisional identity rows, {len(variants):,} tradition-specific candidate variants.",
          f"- UTF-8 candidate texts: {unicode_records:,}; with Devanāgarī: {devanagari_records:,}; still showing broken `(cid:…)` glyph mappings: {cid_records:,}.",
          f"- Padapāṭha records: {pad_rows:,}; status counts: `{dict(pad_counts)}`; rows with word tokens: {fabricated_tokens}; publishable: 0.",
          "- Candidate address counts are not a verified coverage count and must not be used to claim corpus completeness.", "",
          "## Integration checks", "", "- Identity rows remain separate from Kanchi/Sringeri variants; profile keys are valid and no variant references a missing identity: " + str(identity_separation_ok),
          "- Every profile/Maṇḍala has at least one provisional reference candidate: " + str(all(bool(candidate_unique_refs[p] and any(REF.fullmatch(ref) and int(REF.fullmatch(ref).group(1)) == m for ref in candidate_unique_refs[p]) for m in range(1, 11)) for p in ("Kanchi", "Sringeri"))),
          "- Non-fixture source audio files: " + str(len(audio_files)),
          "- Validated profile audio: 0; all absent assets must remain unavailable.",
          "- Production Sanskrit ASR/forced alignment/pronunciation/svara provider: none; evaluation confidence and feature recognition were not testable.", "",
          "## Production-readiness blockers", ""]
    md.extend(f"- {gap}" for gap in report["coverage_gaps"])
    (OUT / "coverage_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(OUT / "coverage_report.md"), "sources": len(sources),
                      "checksum_matches": report["source_files"]["sha256_match_count"],
                      "candidate_rows": candidate_count, "identity_rows": len(identities), "variant_rows": len(variants),
                      "padapatha_rows": pad_rows, "padapatha_statuses": dict(pad_counts), "audio_files": len(audio_files)}, ensure_ascii=False))
    return 0 if source_ok and structure_ok and identity_separation_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
