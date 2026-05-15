#!/usr/bin/env python3
"""
Auto-generate markdown tables for report.md appendices.

Reads from data/bottleneck-analysis.json and invocation-analysis.json,
then updates the placeholder regions in report.md between marker comments.

Usage: python3 scripts/generate-tables.py [--report REPORT_PATH]
"""

import argparse
import json
import os
import re
import sys


def load_json(path):
    with open(path) as f:
        return json.load(f)


def short_name(repo):
    """Get a display-friendly short name for a repo."""
    special = {
        "dotnet/fsharp": "dotnet/fsharp",
        "openclaw/openclaw-windows-node": "openclaw",
    }
    if repo in special:
        return special[repo]
    if "/" in repo:
        return repo.split("/")[1]
    return repo


def generate_throughput_table(bottleneck_data):
    """Generate the Repository Throughput Analysis table from bottleneck-analysis.json."""
    # Sort: BLOCKED first, then FLOWING, then COMMENT-ONLY, then IDLE
    status_order = {"BLOCKED": 0, "FLOWING": 1, "COMMENT-ONLY": 2, "IDLE": 3}

    def sort_key(r):
        status = r.get("bottleneck_status", "FLOWING")
        # Treat repos with 0 RA PRs as COMMENT-ONLY
        if r.get("ra_prs_total", 0) == 0:
            status = "COMMENT-ONLY"
        return (status_order.get(status, 9), -r.get("ra_prs_total", 0))

    rows = sorted(bottleneck_data, key=sort_key)

    lines = []
    lines.append("| Repository | Comment Path (closed/total) | RA PRs | Merged | Rejected | Open (WIP) | PR Throughput | Status |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for r in rows:
        repo = short_name(r["repo"])
        cp_closed = r.get("comment_path_closed", 0)
        cp_total = r.get("comment_path_total", 0)
        ra_total = r.get("ra_prs_total", 0)
        merged = r.get("ra_prs_merged", 0)
        rejected = r.get("ra_prs_closed_unmerged", 0)
        wip = r.get("ra_prs_open", 0)
        status = r.get("bottleneck_status", "FLOWING")

        if ra_total == 0:
            throughput_str = "—"
            merged_str = "—"
            rejected_str = "—"
            wip_str = "—"
            status = "COMMENT-ONLY"
        else:
            ratio = merged / ra_total * 100
            throughput_str = f"{ratio:.0f}%"
            if status == "BLOCKED":
                throughput_str = f"**{throughput_str}**"
            elif ratio == 100:
                throughput_str = f"**{throughput_str}**"
            merged_str = str(merged)
            rejected_str = str(rejected)
            wip_str = str(wip)

        if status == "BLOCKED":
            status_str = f"**{status}**"
        else:
            status_str = status

        lines.append(
            f"| {repo} | {cp_closed}/{cp_total} | {ra_total} | {merged_str} | "
            f"{rejected_str} | {wip_str} | {throughput_str} | {status_str} |"
        )

    return "\n".join(lines)


def generate_invocation_table(invocation_data):
    """Generate the Workflow Invocation table from invocation-analysis.json."""
    # Sort by runs/week descending
    rows = sorted(invocation_data, key=lambda r: -r.get("runs_per_week", 0))

    lines = []
    lines.append("| Repository | Active Runs | Runs/wk | Automated (scheduled) | Automated (additional) | Human intervention |")
    lines.append("|---|---|---|---|---|---|")

    for r in rows:
        repo = short_name(r["repo"])
        active = r.get("active_runs", 0)
        rpw = r.get("runs_per_week", 0)
        scheduled = r.get("scheduled_runs", 0)
        extra = r.get("extra_runs", 0)
        human = r.get("repo_assist_runs", 0)

        lines.append(
            f"| {repo} | {active} | {rpw:.1f} | {scheduled} | {extra} | {human} |"
        )

    return "\n".join(lines)


def update_report(report_path, marker_start, marker_end, table_content):
    """Replace content between marker comments in report.md."""
    with open(report_path) as f:
        content = f.read()

    pattern = re.compile(
        rf"({re.escape(marker_start)}\n)(.*?)({re.escape(marker_end)})",
        re.DOTALL,
    )

    if not pattern.search(content):
        print(f"  WARNING: markers {marker_start} ... {marker_end} not found in {report_path}")
        return False

    new_content = pattern.sub(rf"\g<1>{table_content}\n\g<3>", content)

    with open(report_path, "w") as f:
        f.write(new_content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate tables for report.md appendices")
    parser.add_argument("--report", default="report.md", help="Path to report.md")
    parser.add_argument("--data", default="data", help="Path to data directory")
    args = parser.parse_args()

    report_path = args.report
    data_dir = args.data

    # Load bottleneck analysis
    bottleneck_path = os.path.join(data_dir, "bottleneck-analysis.json")
    if not os.path.exists(bottleneck_path):
        print(f"ERROR: {bottleneck_path} not found. Run bottleneck-analysis.py first.")
        sys.exit(1)
    bottleneck_data = load_json(bottleneck_path)

    # Load invocation analysis
    invocation_path = "invocation-analysis.json"
    if not os.path.exists(invocation_path):
        print(f"ERROR: {invocation_path} not found. Run invocation-analysis.py first.")
        sys.exit(1)
    invocation_data = load_json(invocation_path)

    # Generate and insert throughput table
    throughput_table = generate_throughput_table(bottleneck_data)
    ok = update_report(
        report_path,
        "<!-- THROUGHPUT-TABLE-START -->",
        "<!-- THROUGHPUT-TABLE-END -->",
        throughput_table,
    )
    if ok:
        print(f"  Updated throughput table in {report_path}")

    # Generate and insert invocation table
    invocation_table = generate_invocation_table(invocation_data)
    ok = update_report(
        report_path,
        "<!-- INVOCATION-TABLE-START -->",
        "<!-- INVOCATION-TABLE-END -->",
        invocation_table,
    )
    if ok:
        print(f"  Updated invocation table in {report_path}")

    print("Done.")


if __name__ == "__main__":
    main()
