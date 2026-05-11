# Repo Stats

Analysis of the impact of the [repo-assist](https://github.com/githubnext/agentics) workflow on F# open source repository maintenance.

See [report.md](report.md) for the full analysis.

## Quick Start

Download data for a set of GitHub repos and generate analysis:

```bash
# Download data for a single repo
bash scripts/download-github-data.sh OWNER/REPO [OUTPUT_DIR]

# Download data for all configured repos
bash scripts/download-all.sh

# Generate per-repo graphs
bash scripts/generate-all-graphs.sh [MONTHS]

# Run cross-repo analysis and generate report
python3 scripts/analyze-repo-assist.py data --months 6
```

## Requirements

- [GitHub CLI](https://cli.github.com/) (`gh`) — authenticated
- Python 3 with `matplotlib`
- `jq`
