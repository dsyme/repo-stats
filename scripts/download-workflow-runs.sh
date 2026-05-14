#!/usr/bin/env bash
# Download GitHub Actions workflow run data for repo-assist workflows.
# Usage: ./download-workflow-runs.sh
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
    "fsprojects/fantomas"
    "informedica/GenPRES"
)

for REPO in "${REPOS[@]}"; do
    SAFE_NAME=$(echo "$REPO" | tr '/' '-')
    OUTPUT="$DATA_DIR/$SAFE_NAME"
    mkdir -p "$OUTPUT"

    echo "=== $REPO ==="

    # Find repo-assist workflow ID
    WORKFLOW_ID=$(gh api "repos/$REPO/actions/workflows" \
        --jq '.workflows[] | select(.name | test("Repo Assist"; "i")) | .id' 2>/dev/null || true)

    if [[ -z "$WORKFLOW_ID" ]]; then
        echo "  No Repo Assist workflow found, skipping"
        continue
    fi
    echo "  Workflow ID: $WORKFLOW_ID"

    # Download all workflow runs
    echo "  Fetching workflow runs..."
    gh api "repos/$REPO/actions/workflows/$WORKFLOW_ID/runs" \
        --method GET \
        --paginate \
        -f per_page=100 \
        --jq '.workflow_runs[] | {id, created_at, updated_at, event, status, conclusion, run_attempt}' \
        | jq -s '.' \
        > "$OUTPUT/workflow-runs.json"

    RUN_COUNT=$(jq 'length' "$OUTPUT/workflow-runs.json")
    echo "  Downloaded $RUN_COUNT workflow runs"
done

echo "Done."
