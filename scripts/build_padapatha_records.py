#!/usr/bin/env python3
"""Build auditable Padapāṭha records without deriving word boundaries.

The current Kanchi/Sringeri PDFs are Saṃhitā/RCCS sources, not verified
Padapāṭha witnesses. Optional source Padapāṭha JSONL rows are accepted only
when they explicitly identify the mantra and provide word-ordered tokens plus
their provenance. No whitespace-based splitting or automatic sandhi reversal
is performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECON = ROOT / "content" / "reconciliation"
DEFAULT_OUT = ROOT / "content" / "padapatha"


def jsonl(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def read_padapatha_sources(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    if path is None:
        return result
    for row in jsonl(path):
        key = (row.get("identity_key", ""), row.get("profile", "common"))
        if not key[0] or not isinstance(row.get("tokens"), list) or not row["tokens"]:
            raise SystemExit("Padapāṭha input rows require identity_key and a non-empty ordered tokens array")
        provenance = row.get("source_provenance") or {}
        if not provenance.get("source_title") or not provenance.get("source_locator") or not provenance.get("source_sha256"):
            raise SystemExit(f"Padapāṭha source row {key} lacks title, locator, or source_sha256")
        for index, token in enumerate(row["tokens"], 1):
            if not isinstance(token, dict) or not token.get("original_form"):
                raise SystemExit(f"Padapāṭha token {index} for {key} requires original_form")
            if token.get("word_order") != index:
                raise SystemExit(f"Padapāṭha token word_order must be contiguous from 1 for {key}")
        if key in result:
            raise SystemExit(f"Duplicate Padapāṭha source row: {key}")
        result[key] = row
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconciliation", type=Path, default=DEFAULT_RECON)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--padapatha-source", type=Path, help="Optional source-backed Padapāṭha JSONL; see content/padapatha/README.md")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    source_rows = read_padapatha_sources(args.padapatha_source)
    variants = list(jsonl(args.reconciliation / "tradition_variants.jsonl"))
    if not variants:
        raise SystemExit("No tradition_variants.jsonl found; run reconciliation first")

    rows = []
    counts: Counter[str] = Counter()
    for source in variants:
        identity = source["identity_key"]
        profile = source["profile"]
        pad = source_rows.get((identity, profile)) or source_rows.get((identity, "common"))
        tokens = pad["tokens"] if pad else []
        flags = list(source.get("uncertainty_flags") or [])
        if pad is None:
            flags.append("source_padapatha_unavailable")
        else:
            flags.extend(pad.get("uncertainty_flags") or [])
            if pad.get("review_status") not in {"reviewed", "guru_approved", "approved"}:
                flags.append("padapatha_source_not_reviewed")
        status = "source_padapatha_available" if pad else "unavailable"
        if pad and (flags or not tokens):
            status = "uncertain"
        transliteration = pad.get("transliteration") if pad else None
        row = {
            "record_id": hashlib.sha256(f"{identity}|{profile}|{source['source_sha256']}|{source['source_page']}".encode()).hexdigest(),
            "identity_key": identity,
            "profile": profile,
            "source_variant_id": source.get("variant_id"),
            "original_samhita_form": source.get("devanagari_candidate") or source.get("source_text_segment"),
            "samhita_source_form": source.get("source_text_segment"),
            "padapatha_form": pad.get("padapatha_form") if pad else None,
            "word_order": tokens,
            "transliteration": transliteration,
            "transliteration_scheme": pad.get("transliteration_scheme") if pad else None,
            "phonetic_features": pad.get("phonetic_features", []) if pad else [],
            "vowel_length_metadata": pad.get("vowel_length_metadata", []) if pad else [],
            "vedic_accent_metadata": pad.get("vedic_accent_metadata", []) if pad else [],
            "sandhi_relationships": pad.get("sandhi_relationships", []) if pad else [],
            "segmentation_status": status,
            "segmentation_method": "source_padapatha_transcription" if pad else "none",
            "source_provenance": pad.get("source_provenance") if pad else {
                "source_title": source.get("source_pdf"), "source_url": source.get("source_url"),
                "source_sha256": source.get("source_sha256"), "source_page": source.get("source_page"),
                "note": "Source is a Saṃhitā/RCCS candidate; it does not provide verified Padapāṭha segmentation.",
            },
            "samhita_provenance": {"source_pdf": source.get("source_pdf"), "source_url": source.get("source_url"),
                                    "source_sha256": source.get("source_sha256"), "source_page": source.get("source_page"),
                                    "extraction_method": source.get("extraction_method"),
                                    "extraction_confidence": source.get("extraction_confidence")},
            "uncertainty_flags": sorted(set(flags)),
            "publication_allowed": bool(pad and not flags and pad.get("review_status") in {"guru_approved", "approved"}
                                         and source.get("publication_allowed", False)),
        }
        row["record_checksum"] = digest(row)
        counts[status] += 1
        rows.append(row)

    write_jsonl(args.out / "padapatha_records.jsonl", rows)
    fields = list(rows[0].keys())
    with (args.out / "padapatha_records.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})
    (args.out / "padapatha_report.json").write_text(json.dumps({
        "record_count": len(rows), "status_counts": dict(counts), "publishable_count": sum(r["publication_allowed"] for r in rows),
        "source_padapatha_input": str(args.padapatha_source) if args.padapatha_source else None,
        "method": "Only explicit source Padapāṭha tokens are accepted. Samhita text is never segmented by whitespace or inferred sandhi reversal.",
        "scope_note": "Records cover existing provisional source-address variants; unobserved mantra addresses are not synthesized.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "padapatha_schema.sql").write_text(SQL, encoding="utf-8")
    return 0


SQL = r'''CREATE TABLE IF NOT EXISTS rigveda_padapatha (
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
);'''

if __name__ == "__main__":
    raise SystemExit(main())
