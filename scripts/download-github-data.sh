#!/usr/bin/env bash
# Generic script to download all issues and PRs from a GitHub repository as JSON.
# Usage: ./download-github-data.sh [OWNER/REPO] [OUTPUT_DIR]
# Defaults: OWNER/REPO from current git remote, OUTPUT_DIR = ./github-data
# Requires: gh (GitHub CLI), authenticated

set -euo pipefail

# Determine repo
if [[ -n "${1:-}" ]]; then
    REPO="$1"
else
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)
    if [[ -z "$REPO" ]]; then
        echo "Error: Could not detect repo. Pass OWNER/REPO as first argument." >&2
        exit 1
    fi
fi

OUTPUT_DIR="${2:-./github-data}"
mkdir -p "$OUTPUT_DIR"

echo "Downloading data for $REPO into $OUTPUT_DIR ..."

# Download all issues (issues + PRs come together from the issues endpoint,
# but we also fetch PRs separately for PR-specific fields like merge info).
echo "Fetching all issues..."
gh api "repos/$REPO/issues" \
    --paginate \
    --method GET \
    -f state=all \
    -f per_page=100 \
    -f direction=asc \
    --cache 1h \
    | jq -s 'add' \
    > "$OUTPUT_DIR/issues-raw.json"

ISSUE_COUNT=$(jq 'length' "$OUTPUT_DIR/issues-raw.json")
echo "  Downloaded $ISSUE_COUNT issues (including PRs)"

# Split into pure issues and PR stubs
jq '[.[] | select(.pull_request == null)]' "$OUTPUT_DIR/issues-raw.json" > "$OUTPUT_DIR/issues.json"
PURE_ISSUE_COUNT=$(jq 'length' "$OUTPUT_DIR/issues.json")
echo "  Pure issues: $PURE_ISSUE_COUNT"

# Download all PRs with full PR details (merge commit, review info, etc.)
echo "Fetching all pull requests..."
gh api "repos/$REPO/pulls" \
    --paginate \
    --method GET \
    -f state=all \
    -f per_page=100 \
    -f direction=asc \
    --cache 1h \
    | jq -s 'add' \
    > "$OUTPUT_DIR/pulls.json"

PR_COUNT=$(jq 'length' "$OUTPUT_DIR/pulls.json")
echo "  Downloaded $PR_COUNT pull requests"

# Download issue events (opened/closed/reopened) for reconstructing history
echo "Fetching issue events..."
gh api "repos/$REPO/issues/events" \
    --paginate \
    --method GET \
    -f per_page=100 \
    --cache 1h \
    | jq -s 'add' \
    > "$OUTPUT_DIR/issue-events.json"

EVENT_COUNT=$(jq 'length' "$OUTPUT_DIR/issue-events.json")
echo "  Downloaded $EVENT_COUNT issue events"

# Write metadata
jq -n \
    --arg repo "$REPO" \
    --arg date "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --argjson issues "$PURE_ISSUE_COUNT" \
    --argjson prs "$PR_COUNT" \
    --argjson events "$EVENT_COUNT" \
    '{repo: $repo, downloaded_at: $date, issue_count: $issues, pr_count: $prs, event_count: $events}' \
    > "$OUTPUT_DIR/metadata.json"

echo "Done. Data saved to $OUTPUT_DIR/"
echo "Files: issues.json, pulls.json, issue-events.json, issues-raw.json, metadata.json"
