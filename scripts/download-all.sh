#!/usr/bin/env bash
# Download GitHub data for multiple repositories.
# Usage: ./download-all.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$(dirname "$SCRIPT_DIR")/data"

REPOS=(
    "fsprojects/FSharp.Control.AsyncSeq"
    "fsprojects/FSharp.Data"
    "fslaborg/Deedle"
    "fsprojects/FSharp.Control.TaskSeq"
    "fsprojects/FSharp.Formatting"
    "ionide/FsAutoComplete"
    "fsprojects/FSharp.TypeProviders.SDK"
    "fslaborg/FSharp.Stats"
    "fsprojects/SwaggerProvider"
    "py-why/dowhy"
)

for REPO in "${REPOS[@]}"; do
    SAFE_NAME=$(echo "$REPO" | tr '/' '-')
    OUTPUT="$DATA_DIR/$SAFE_NAME"
    
    if [[ -f "$OUTPUT/metadata.json" ]]; then
        echo "=== Skipping $REPO (already downloaded) ==="
        continue
    fi
    
    echo "=== Downloading $REPO ==="
    bash "$SCRIPT_DIR/download-github-data.sh" "$REPO" "$OUTPUT"
    echo ""
done

echo "All downloads complete."
