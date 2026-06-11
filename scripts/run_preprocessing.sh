#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${1:-data/sample/cert-r4.2-small}"

python ml/ueba_ml/pipelines/preprocess.py --input-dir "$INPUT_DIR"
