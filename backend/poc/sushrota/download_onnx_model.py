"""Download the public Su-śrotā ONNX POC artifacts to a local model cache."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import urlretrieve


REPOSITORY = "https://huggingface.co/gnumanth/sushrota-sanskrit-asr-onnx/resolve/main"
FILES = (
    "preprocessor.onnx",
    "sushrota_sanskrit_ctc_int8.onnx",
    "sanskrit_vocab.json",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    args = parser.parse_args()
    args.model_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = args.model_dir / name
        if not target.exists():
            urlretrieve(f"{REPOSITORY}/{name}?download=true", target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f"{name}\t{target.stat().st_size}\t{digest}")


if __name__ == "__main__":
    main()
