#!/usr/bin/env bash
# Generate graphs for all downloaded repos.
# Usage: ./generate-all-graphs.sh [MONTHS]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"
GRAPHS_DIR="$(dirname "$SCRIPT_DIR")/graphs"
MONTHS="${1:-6}"

for REPO_DIR in "$DATA_DIR"/*/; do
    REPO_NAME=$(basename "$REPO_DIR")
    OUTPUT="$GRAPHS_DIR/$REPO_NAME"
    mkdir -p "$OUTPUT"
    
    echo "=== Generating graphs for $REPO_NAME ==="
    python3 "$SCRIPT_DIR/graph-repo-stats.py" "$REPO_DIR" --output "$OUTPUT" --months "$MONTHS"
    echo ""
done

echo "All graphs generated in $GRAPHS_DIR/"
