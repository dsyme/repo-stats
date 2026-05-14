#!/usr/bin/env bash
# Download issue comments for all repos (for repo-assist comment-path analysis).
# Only downloads comments from github-actions[bot] to keep data manageable.
# Usage: ./download-issue-comments.sh
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
    echo "  Fetching issue comments..."
    gh api "repos/$REPO/issues/comments" \
        --method GET \
        --paginate \
        -f per_page=100 \
        -f sort=created \
        -f direction=desc \
        --jq '[.[] | select(.user.login == "github-actions[bot]") | {id, issue_url, created_at, body: .body}]' \
        | jq -s 'add // []' \
        > "$OUTPUT/bot-comments.json"

    COUNT=$(jq 'length' "$OUTPUT/bot-comments.json")
    echo "  Downloaded $COUNT bot comments"
done

echo "Done."
