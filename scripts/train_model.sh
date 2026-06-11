#!/usr/bin/env bash
set -euo pipefail

python ml/ueba_ml/pipelines/train.py "$@"
