#!/usr/bin/env bash
set -euo pipefail
echo "=== Starting Omarchy Custom ISO Studio ==="
python3 omarchy_builder.py "$@"