#!/usr/bin/env bash
set -euo pipefail

python src/services/ueba_ml/pipelines/train.py "$@"
