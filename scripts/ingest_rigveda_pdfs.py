#!/usr/bin/env python3
"""Auditable, page-preserving ingestion for the Kanchi/Sringeri Rigveda PDFs.

The text layer in these PDFs may use broken font maps. This script never repairs
Sanskrit. It keeps extracted text verbatim, emits NFC as a separate derivative,
and uses Tesseract OCR only for pages whose text layer is unusable. Pages needing
OCR are marked for review if Tesseract or its Hindi/English data are unavailable.

Requires pdfplumber. Optional OCR: Poppler pdftoppm and Tesseract with hin+eng.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pdfplumber
except ImportError as exc:  # pragma: no cover - actionable CLI error
    raise SystemExit("pdfplumber is required; install it in the selected Python environment") from exc

DEFAULT_KANCHI = Path(r"C:\Users\ZMIT\Downloads\rigvedas")
DEFAULT_SRINGERI = Path(r"C:\Users\ZMIT\Downloads\sringeri")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "content" / "ingestion"

DEVANAGARI = re.compile(r"[\u0900-\u097f\ua8e0-\ua8ff]")
LATIN = re.compile(r"[A-Za-zĀ-ž]" )
CID = re.compile(r"\(cid:\d+\)")
REF = re.compile(r"(?<!\d)(\d{1,2})\s*[.।]\s*(\d{1,3})(?:\s*[–-]\s*(\d{1,2})\s*[.।]\s*(\d{1,3}))?")
VEDIC_MARK_RANGES = ((0x0951, 0x0954), (0x1CD0, 0x1CFF), (0xA8E0, 0xA8FF))
CSV_FIELDS = [
    "profile", "mandala", "source_pdf", "source_sha256", "source_page",
    "unit_kind", "sukta_references_json", "mantra_reference_candidates_json", "raw_text", "normalized_text",
    "devanagari_text", "rccs_text_candidate", "romanized_sanskrit_iast_candidate", "transliteration_candidate",
    "svara_marks_json", "rccs_visual_cues_json", "extraction_method", "confidence", "ocr_confidence",
    "review_status", "uncertainty_flags_json",
]
MANTRA_FIELDS = [
    "profile", "mandala", "source_pdf", "source_sha256", "source_page",
    "reference_candidate", "sukta_reference_candidates_json", "mantra_number_candidate",
    "verse_marker_evidence", "source_text_segment", "devanagari_candidate", "rccs_text_candidate", "romanized_sanskrit_iast_candidate",
    "transliteration_candidate", "svara_marks_json", "extraction_method",
    "segmentation_method", "confidence", "ocr_confidence", "review_status",
    "uncertainty_flags_json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def svara_marks(text: str) -> list[dict[str, Any]]:
    counts = Counter(ord(ch) for ch in text if any(lo <= ord(ch) <= hi for lo, hi in VEDIC_MARK_RANGES))
    return [{"codepoint": f"U+{cp:04X}", "character": chr(cp), "count": count} for cp, count in sorted(counts.items())]


def rccs_visual_cues(page: Any) -> list[dict[str, Any]]:
    """Preserve non-black RCCS glyph styling and position without interpreting it."""
    glyphs: list[dict[str, Any]] = []
    for ch in page.chars:
        color = ch.get("non_stroking_color")
        if not isinstance(color, (tuple, list)) or len(color) < 3:
            continue
        rgb = tuple(round(float(v), 4) for v in color[:3])
        if rgb == (0.0, 0.0, 0.0):
            continue
        glyphs.append({
            "text": ch.get("text", ""), "rgb": rgb,
            "x0": round(float(ch.get("x0", 0)), 2), "top": round(float(ch.get("top", 0)), 2),
            "x1": round(float(ch.get("x1", 0)), 2),
            "font": ch.get("fontname"), "size": round(float(ch.get("size", 0)), 2),
        })
    spans: list[dict[str, Any]] = []
    for glyph in glyphs:
        if spans:
            last = spans[-1]
            gap = glyph["x0"] - last["x1"]
            if (glyph["rgb"] == last["rgb"] and glyph["font"] == last["font"]
                    and glyph["size"] == last["size"] and abs(glyph["top"] - last["top"]) <= 0.7
                    and -0.5 <= gap <= max(12.0, glyph["size"] * 1.8)):
                last["text"] += glyph["text"]
                last["x1"] = glyph["x1"]
                continue
        spans.append(glyph.copy())
    return spans


def refs(text: str, mandala: int) -> list[str]:
    counts: Counter[str] = Counter()
    for m in REF.finditer(text):
        a, b, c, d = m.groups()
        # The source pages often print both Devanagari and Arabic numerals in
        # running headers. Keep only references scoped to this source volume.
        if int(a) == mandala:
            item = f"RV.{int(a):02d}.{int(b):03d}"
            counts[item] += 1
        elif c and int(c) == mandala:
            item = f"RV.{int(c):02d}.{int(d):03d}"
            counts[item] += 1
    if not counts:
        return []
    highest = max(counts.values())
    # Repeated running headers/footer are stronger current-page evidence than a
    # one-off cover/index range. Ties remain explicitly ambiguous.
    return [key for key, value in counts.items() if value == highest]


def mantra_refs(text: str, sukta_references: list[str]) -> list[dict[str, Any]]:
    """Return only explicit verse-number cues; never fill a sequence by inference."""
    candidates: list[dict[str, Any]] = []
    markers = re.compile(r"(?:॥\s*[.।]?\s*([0-9०-९]+)\s*॥|\|\|\s*([0-9०-९]+)\s*\|\|)")
    seen: dict[tuple[str | None, int], dict[str, Any]] = {}
    for m in markers.finditer(text):
        numeral = m.group(1) or m.group(2)
        try:
            verse = int(numeral)
        except (ValueError, TypeError):
            continue
        if verse <= 0:
            continue
        ref = f"{sukta_references[0]}.{verse:02d}" if len(sukta_references) == 1 else None
        key = (ref, verse)
        item = seen.get(key)
        if item is None:
            item = {"reference": ref, "sukta_reference_candidates": list(sukta_references),
                    "mantra_number_candidate": verse, "evidence": [],
                    "confidence": 0.2 if ref else 0.05,
                    "status": "heuristic_unverified" if ref else "ambiguous_sukta_reference"}
            seen[key] = item
            candidates.append(item)
        if m.group(0) not in item["evidence"]:
            item["evidence"].append(m.group(0))
    return candidates


def split_mantra_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Split only at explicit verse-end markers; otherwise retain a page candidate."""
    text = row["normalized_text"]
    marker_re = re.compile(r"(?:॥\s*[.।]?\s*([0-9०-९]+)\s*॥|\|\|\s*([0-9०-९]+)\s*\|\|)")
    markers = list(marker_re.finditer(text))
    refs_here = row["sukta_references"]
    candidates: list[dict[str, Any]] = []
    if not markers:
        segments = [(0, len(text), None, None)]
    else:
        segments = []
        start = 0
        i = 0
        while i < len(markers):
            match = markers[i]
            try:
                verse_no = int(match.group(1) or match.group(2))
            except (ValueError, TypeError):
                verse_no = None
            end_marker = match
            # The source prints each verse in Devanagari and RCCS; both forms
            # carry an end marker with the same number. Pair adjacent matches
            # to produce one bilingual candidate instead of duplicate rows.
            if i + 1 < len(markers):
                next_marker = markers[i + 1]
                try:
                    next_no = int(next_marker.group(1) or next_marker.group(2))
                except (ValueError, TypeError):
                    next_no = None
                if verse_no is not None and next_no == verse_no:
                    end_marker = next_marker
                    i += 1
            evidence = match.group(0) if end_marker is match else match.group(0) + " / " + end_marker.group(0)
            segments.append((start, end_marker.end(), verse_no, evidence))
            start = end_marker.end()
            i += 1
    for start, end, verse_no, evidence in segments:
        segment = text[start:end].strip()
        flags = list(row["uncertainty_flags"])
        flags.append("heuristic_candidate_segmentation")
        if not markers:
            flags.append("mantra_marker_not_detected")
        if len(refs_here) != 1:
            flags.append("sukta_reference_ambiguous_or_missing")
        if len(refs_here) == 1 and verse_no is not None:
            reference = f"{refs_here[0]}.{verse_no:02d}"
        else:
            reference = None
        if evidence:
            flags.append("verse_end_marker_candidate")
        devanagari = "\n".join(line for line in segment.splitlines() if DEVANAGARI.search(line))
        roman = "\n".join(line for line in segment.splitlines() if LATIN.search(line))
        if not devanagari:
            flags.append("no_devanagari_in_candidate_segment")
        if not roman:
            flags.append("no_romanized_text_in_candidate_segment")
        candidates.append({
            "profile": row["profile"], "mandala": row["mandala"],
            "source_pdf": row["source_pdf"], "source_sha256": row["source_sha256"],
            "source_page": row["source_page"], "reference_candidate": reference,
            "sukta_reference_candidates": refs_here, "mantra_number_candidate": verse_no,
            "verse_marker_evidence": evidence, "source_text_segment": segment,
            "devanagari_candidate": devanagari,
            "rccs_text_candidate": roman,
            "romanized_sanskrit_iast_candidate": roman,
            "transliteration_candidate": roman,
            "svara_marks": svara_marks(segment),
            "extraction_method": row["extraction_method"],
            "segmentation_method": "verse_end_marker_heuristic" if markers else "whole_page_unsegmented",
            "confidence": round(min(row["confidence"], 0.2) if markers else 0.0, 4),
            "ocr_confidence": row["ocr_confidence"], "review_status": "needs_human_review",
            "uncertainty_flags": sorted(set(flags)),
        })
    return candidates


def analyze_layer(text: str) -> tuple[float, list[str], str, str, list[dict[str, Any]]]:
    flags: list[str] = []
    cid_count = len(CID.findall(text))
    dev_count = len(DEVANAGARI.findall(text))
    meaningful = sum(ch.isalpha() for ch in text)
    if len(text.strip()) < 80:
        flags.append("text_layer_sparse")
    if cid_count:
        flags.append("broken_font_mapping_cid_placeholders")
    # A useful page-level Devanagari layer should not be dominated by CIDs or
    # missing-script Latin substitutions. This is only a routing heuristic.
    ratio = dev_count / max(meaningful, 1)
    if dev_count < 80 or ratio < 0.18 or cid_count > max(3, dev_count // 4):
        flags.append("text_layer_unreliable_ocr_needed")
    confidence = max(0.0, min(0.35, 0.35 * min(1.0, dev_count / 250) * (1 - min(0.95, cid_count / max(meaningful, 1)))))
    devanagari = "\n".join(line for line in text.splitlines() if DEVANAGARI.search(line))
    roman_lines = "\n".join(line for line in text.splitlines() if LATIN.search(line))
    marks = svara_marks(text)
    if not marks:
        flags.append("svara_marks_not_detected_or_unmapped")
    return confidence, flags, devanagari, roman_lines, marks


def run_ocr(pdf: Path, page_num: int, poppler: str, tesseract: str, lang: str) -> tuple[str, float | None, str | None]:
    with tempfile.TemporaryDirectory(prefix="rv_ocr_") as tmp:
        prefix = Path(tmp) / "page"
        cmd = [poppler, "-f", str(page_num), "-l", str(page_num), "-r", "350", "-png", str(pdf), str(prefix)]
        render = subprocess.run(cmd, capture_output=True, text=True)
        if render.returncode:
            return "", None, "pdf_render_failed: " + (render.stderr.strip()[-500:])
        images = list(Path(tmp).glob("page-*.png"))
        if not images:
            return "", None, "pdf_render_produced_no_image"
        base = [tesseract, str(images[0]), "stdout", "-l", lang, "--psm", "6"]
        txt = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if txt.returncode:
            return "", None, "tesseract_failed: " + txt.stderr.strip()[-500:]
        tsv = subprocess.run([tesseract, str(images[0]), "stdout", "-l", lang, "--psm", "6", "tsv"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        confs: list[float] = []
        if tsv.returncode == 0:
            for line in tsv.stdout.splitlines()[1:]:
                cols = line.split("\t")
                if len(cols) > 10 and cols[10].strip() and cols[10] != "-1":
                    try:
                        confs.append(float(cols[10]) / 100)
                    except ValueError:
                        pass
        return txt.stdout.rstrip("\r\n"), (sum(confs) / len(confs) if confs else None), None


def make_row(profile: str, mandala: int, pdf: Path, file_hash: str, page_num: int,
             raw: str, method: str, confidence: float, ocr_conf: float | None,
             flags: list[str], visual_cues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    normalized = nfc(raw)
    dev = "\n".join(line for line in normalized.splitlines() if DEVANAGARI.search(line))
    roman = "\n".join(line for line in normalized.splitlines() if LATIN.search(line))
    marks = svara_marks(normalized)
    page_refs = refs(normalized, mandala)
    page_mantras = mantra_refs(normalized, page_refs)
    if not page_refs:
        flags.append("mantra_reference_not_confidently_parsed")
    if not dev:
        flags.append("no_devanagari_extracted")
    if not roman:
        flags.append("no_romanized_text_extracted")
    if not marks:
        flags.append("svara_marks_not_detected_or_unmapped")
    return {
        "profile": profile,
        "mandala": mandala,
        "source_pdf": str(pdf),
        "source_sha256": file_hash,
        "source_page": page_num,
        "unit_kind": "source_page_extraction",
        "sukta_references": page_refs,
        "mantra_reference_candidates": page_mantras,
        "raw_text": raw,
        "normalized_text": normalized,
        "devanagari_text": dev,
        "rccs_text_candidate": roman,
        "romanized_sanskrit_iast_candidate": roman,
        "transliteration_candidate": roman,
        "svara_marks": marks,
        "rccs_visual_cues": visual_cues or [],
        "extraction_method": method,
        "confidence": round(confidence, 4),
        "ocr_confidence": round(ocr_conf, 4) if ocr_conf is not None else None,
        "review_status": "needs_human_review" if flags else "machine_extracted_unreviewed",
        "uncertainty_flags": sorted(set(flags)),
    }


def pdf_info(pdf: Path, pdfinfo: str | None) -> dict[str, Any]:
    info: dict[str, Any] = {}
    if pdfinfo:
        p = subprocess.run([pdfinfo, str(pdf)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode == 0:
            for line in p.stdout.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    info[k.strip()] = v.strip()
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kanchi-dir", type=Path, default=DEFAULT_KANCHI)
    ap.add_argument("--sringeri-dir", type=Path, default=DEFAULT_SRINGERI)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--ocr", choices=("auto", "off"), default="auto")
    ap.add_argument("--ocr-lang", default="hin+eng", help="Tesseract languages; default hin+eng")
    ap.add_argument("--start-page", type=int, default=1, help="1-based inclusive page for resuming/targeted runs")
    ap.add_argument("--end-page", type=int, help="1-based inclusive page limit for targeted runs")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tesseract = shutil.which("tesseract") if args.ocr == "auto" else None
    poppler = shutil.which("pdftoppm") if args.ocr == "auto" else None
    ocr_ready = bool(tesseract and poppler)
    tesseract_languages: set[str] = set()
    if ocr_ready:
        lang_proc = subprocess.run([tesseract, "--list-langs"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        tesseract_languages = set(lang_proc.stdout.split())
        required = set(args.ocr_lang.split("+"))
        ocr_ready = lang_proc.returncode == 0 and required.issubset(tesseract_languages)

    pdfinfo = shutil.which("pdfinfo")
    inputs = [("Kanchi", args.kanchi_dir, "_kp.pdf"), ("Sringeri", args.sringeri_dir, "_sp.pdf")]
    sources: list[dict[str, Any]] = []
    json_path = args.out / "pages.jsonl"
    csv_path = args.out / "pages.csv"
    mantra_json_path = args.out / "mantra_candidates.jsonl"
    mantra_csv_path = args.out / "mantra_candidates.csv"
    count = 0
    mantra_count = 0
    started = datetime.now(timezone.utc).isoformat()
    with json_path.open("w", encoding="utf-8", newline="\n") as jf, csv_path.open("w", encoding="utf-8-sig", newline="") as cf, \
         mantra_json_path.open("w", encoding="utf-8", newline="\n") as mjf, mantra_csv_path.open("w", encoding="utf-8-sig", newline="") as mcf:
        writer = csv.DictWriter(cf, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        mantra_writer = csv.DictWriter(mcf, fieldnames=MANTRA_FIELDS, quoting=csv.QUOTE_ALL)
        mantra_writer.writeheader()
        for profile, folder, suffix in inputs:
            if not folder.is_dir():
                raise SystemExit(f"Source folder not found: {folder}")
            pdfs = sorted(folder.glob(f"*{suffix}"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else p.name)
            if len(pdfs) != 10:
                print(f"WARNING: {profile}: expected 10 PDFs, found {len(pdfs)}", file=sys.stderr)
            for pdf in pdfs:
                m = re.search(r"(\d+)", pdf.stem)
                if not m:
                    print(f"WARNING: cannot infer mandala from filename {pdf.name}; skipped", file=sys.stderr)
                    continue
                mandala = int(m.group(1))
                file_hash = sha256(pdf)
                info = pdf_info(pdf, pdfinfo)
                with pdfplumber.open(str(pdf)) as doc:
                    source = {
                        "profile": profile,
                        "mandala": mandala,
                        "file": str(pdf),
                        "source_url": f"https://www.saiveda.net/textes/maNDala_{mandala:02d}_{'kp' if profile == 'Kanchi' else 'sp'}.pdf",
                        "source_index_url": "https://www.saiveda.net/en/rigveda.html",
                        "rccs_definition_url": "https://www.saiveda.net/en/rccs.html",
                        "sha256": file_hash,
                        "pdf_metadata": doc.metadata,
                        "pdfinfo": info,
                        "page_count": len(doc.pages),
                        "edition": "Not identified in PDF metadata; metadata title is SaiVeda",
                        "provenance": "User-supplied local PDF; PDF metadata author www.saiveda.net; producer Ghostscript 8.71",
                        "license_status": "No reuse license identified in reviewed page/PDF metadata; PDF permissions report copy:no; obtain written rights confirmation before redistribution",
                        "pdf_copy_permission": "no" if re.search(r"copy\s*:\s*no", info.get("Encrypted", ""), re.I) else "not reported",
                        "pdf_print_permission": "yes" if re.search(r"print\s*:\s*yes", info.get("Encrypted", ""), re.I) else "not reported",
                    }
                    sources.append(source)
                    lo = max(1, args.start_page)
                    hi = min(len(doc.pages), args.end_page or len(doc.pages))
                    for page_num in range(lo, hi + 1):
                        page_obj = doc.pages[page_num - 1]
                        try:
                            extracted = page_obj.extract_text(layout=False) or ""
                        except Exception as exc:  # retain page provenance even on parser errors
                            extracted = ""
                            flags = ["embedded_text_extraction_error", "text_layer_unreliable_ocr_needed", f"parser_error:{type(exc).__name__}"]
                            layer_conf = 0.0
                        else:
                            layer_conf, flags, _, _, _ = analyze_layer(extracted)
                        raw = extracted
                        method = "embedded_text"
                        ocr_conf: float | None = None
                        if "text_layer_unreliable_ocr_needed" in flags:
                            if args.ocr == "off":
                                flags.append("ocr_disabled_by_option")
                            elif not ocr_ready:
                                flags.append("ocr_engine_or_required_language_data_unavailable")
                            else:
                                ocr_text, ocr_conf, ocr_error = run_ocr(pdf, page_num, poppler, tesseract, args.ocr_lang)
                                if ocr_error:
                                    flags.append(ocr_error)
                                elif ocr_text.strip():
                                    # OCR replaces the unusable layer only in normalized
                                    # candidate fields; embedded text remains preserved.
                                    raw = extracted
                                    method = "embedded_text+ocr"
                                    flags.append("ocr_output_unreviewed")
                                    if ocr_conf is not None and ocr_conf < 0.72:
                                        flags.append("low_ocr_confidence")
                                    row = make_row(profile, mandala, pdf, file_hash, page_num, ocr_text, method,
                                                   min(0.99, ocr_conf or 0.0), ocr_conf, flags,
                                                   rccs_visual_cues(page_obj))
                                    row["raw_text"] = extracted
                                    row["ocr_text"] = ocr_text
                                else:
                                    flags.append("ocr_returned_empty_text")
                        if method == "embedded_text+ocr":
                            pass
                        else:
                            row = make_row(profile, mandala, pdf, file_hash, page_num, raw, method, layer_conf, ocr_conf, flags,
                                           rccs_visual_cues(page_obj))
                        jf.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                        csvrow = {k: row.get(k) for k in CSV_FIELDS}
                        csvrow["sukta_references_json"] = json.dumps(row["sukta_references"], ensure_ascii=False)
                        csvrow["mantra_reference_candidates_json"] = json.dumps(row["mantra_reference_candidates"], ensure_ascii=False)
                        csvrow["svara_marks_json"] = json.dumps(row["svara_marks"], ensure_ascii=False)
                        csvrow["rccs_visual_cues_json"] = json.dumps(row["rccs_visual_cues"], ensure_ascii=False)
                        csvrow["uncertainty_flags_json"] = json.dumps(row["uncertainty_flags"], ensure_ascii=False)
                        writer.writerow(csvrow)
                        for candidate in split_mantra_candidates(row):
                            mjf.write(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")) + "\n")
                            mrow = {k: candidate.get(k) for k in MANTRA_FIELDS}
                            mrow["sukta_reference_candidates_json"] = json.dumps(candidate["sukta_reference_candidates"], ensure_ascii=False)
                            mrow["svara_marks_json"] = json.dumps(candidate["svara_marks"], ensure_ascii=False)
                            mrow["uncertainty_flags_json"] = json.dumps(candidate["uncertainty_flags"], ensure_ascii=False)
                            mantra_writer.writerow(mrow)
                            mantra_count += 1
                        count += 1
                        if count % 100 == 0:
                            jf.flush(); cf.flush(); mjf.flush(); mcf.flush()
                            print(f"Processed {count} pages; latest {profile} Mandala {mandala:02d} page {page_num}", file=sys.stderr)

    manifest = {
        "schema_version": "1.0",
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "page_records_written": count,
        "mantra_candidates_written": mantra_count,
        "source_pdf_count": len(sources),
        "ocr_requested": args.ocr,
        "ocr_available": ocr_ready,
        "ocr_languages_requested": args.ocr_lang,
        "tesseract_languages_available": sorted(tesseract_languages),
        "limitations": [
            "Page-level records are extraction candidates, not guru-reviewed mantras.",
            "Normalized text applies Unicode NFC only; no Sanskrit correction, transliteration, or svara inference is performed.",
            "Sūkta references are heuristic candidates from page text and require verification.",
            "PDF metadata does not establish publication edition, license, or authenticity.",
            "RCCS source text and non-black glyph color/vertical-position cues are preserved; color semantics are not inferred. The IAST field is an unconverted source transliteration candidate, not normalized IAST.",
        ],
        "sources": sources,
    }
    artifacts = [json_path, csv_path, mantra_json_path, mantra_csv_path, args.out / "postgres_import.sql"]
    manifest["generated_artifacts"] = [
        {"file": p.name, "sha256": sha256(p), "size_bytes": p.stat().st_size}
        for p in artifacts if p.exists()
    ]
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / "postgres_import.sql").write_text(POSTGRES_SQL, encoding="utf-8")
    print(f"Wrote {count} page records to {args.out}")
    print(f"OCR available: {ocr_ready}; review OCR uncertainty flags before use")
    return 0


POSTGRES_SQL = r'''-- PostgreSQL staging import for pages.csv. Run from the ingestion output folder.
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
'''

if __name__ == "__main__":
    raise SystemExit(main())
