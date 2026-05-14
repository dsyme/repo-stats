#!/usr/bin/env python3
"""
Generate a normalized open-issues-over-time graph aligned to repo-assist adoption date.

Y-axis: open issues as % of open issues at adoption date (100% = adoption day)
X-axis: days before/after adoption (0 = adoption day)

Each repo is a separate line, allowing visual comparison of trajectories.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
from chart_theme import make_figure, save_figure, add_adoption_vline_at_zero, COLORS, PALETTE, STATUS_COLORS


def parse_dt(s):
    if s is None:
        return None
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def detect_repo_assist_adoption(data_dir):
    pulls = load_json(os.path.join(data_dir, "pulls.json"))
    issues_raw = load_json(os.path.join(data_dir, "issues-raw.json"))
    ra_dates = []
    for pr in pulls:
        title = pr.get("title", "")
        labels = [l.get("name", "") for l in pr.get("labels", [])]
        if "[repo-assist]" in title or "[Repo Assist]" in title or "repo-assist" in labels:
            dt = parse_dt(pr.get("created_at"))
            if dt:
                ra_dates.append(dt)
    for issue in issues_raw:
        labels = [l.get("name", "") for l in issue.get("labels", [])]
        title = issue.get("title", "")
        if "repo-assist" in labels or "[repo-assist]" in title or "[Repo Assist]" in title:
            dt = parse_dt(issue.get("created_at"))
            if dt:
                ra_dates.append(dt)
    return min(ra_dates) if ra_dates else None


def compute_open_issues_timeline(data_dir, day_range=(-90, 90)):
    """Compute daily open issue count relative to adoption date."""
    meta = load_json(os.path.join(data_dir, "metadata.json"))
    issues = load_json(os.path.join(data_dir, "issues.json"))
    adoption = detect_repo_assist_adoption(data_dir)

    if not adoption:
        return None

    repo_name = meta.get("repo", os.path.basename(data_dir))
    now = datetime.now(timezone.utc)

    # Build list of (created_date, closed_date) for all issues
    issue_events = []
    for issue in issues:
        created = parse_dt(issue["created_at"])
        closed = parse_dt(issue.get("closed_at"))
        if created:
            issue_events.append((created, closed))

    # For each day in range, count open issues
    days = []
    counts = []
    for day_offset in range(day_range[0], day_range[1] + 1):
        target = adoption + timedelta(days=day_offset)
        if target > now:
            break

        open_count = 0
        for created, closed in issue_events:
            if created <= target:
                if closed is None or closed > target:
                    open_count += 1

        days.append(day_offset)
        counts.append(open_count)

    # Normalize: find open count at adoption (day 0)
    open_at_adoption = None
    for d, c in zip(days, counts):
        if d == 0:
            open_at_adoption = c
            break

    if not open_at_adoption or open_at_adoption == 0:
        return None

    normalized = [c / open_at_adoption * 100 for c in counts]

    return {
        "repo": repo_name,
        "days": days,
        "counts": counts,
        "normalized": normalized,
        "open_at_adoption": open_at_adoption,
        "adoption_date": adoption.strftime("%Y-%m-%d"),
    }


def generate_graph(all_timelines, output_path, bottleneck_data=None):
    """Generate the multi-line normalized graph."""
    fig = make_figure(
        title="Open Issue Trajectories Normalized to Adoption Date<br>"
              "<sup>each line = one repository, 100% = open issues at adoption, dashed = blocked pipeline</sup>",
        width=1200,
        height=700,
    )

    # Load bottleneck status for coloring if available
    bottleneck_status = {}
    if bottleneck_data:
        for r in bottleneck_data:
            bottleneck_status[r["repo"]] = r.get("bottleneck_status", "FLOWING")

    # Sort by final normalized value (most reduction first)
    all_timelines.sort(key=lambda t: t["normalized"][-1])

    for i, tl in enumerate(all_timelines):
        repo_short = tl["repo"].split("/")[1] if "/" in tl["repo"] else tl["repo"]
        status = bottleneck_status.get(tl["repo"], "FLOWING")

        label = f"{repo_short}"
        if status == "BLOCKED":
            label += " ⊘"

        color = PALETTE[i % len(PALETTE)]
        line_dash = "dash" if status == "BLOCKED" else "solid"

        fig.add_trace(go.Scatter(
            x=tl["days"],
            y=tl["normalized"],
            mode="lines",
            name=label,
            line=dict(color=color, width=2, dash=line_dash),
            opacity=0.8,
        ))

    # Adoption vertical line at x=0
    add_adoption_vline_at_zero(fig)

    # 100% reference line
    fig.add_hline(
        y=100, line_dash="dot", line_color="gray", line_width=1, opacity=0.5,
    )

    fig.update_layout(
        xaxis_title="Days Before / After Repo-Assist Adoption",
        yaxis_title="Open Issues (% of count at adoption)",
        yaxis_ticksuffix="%",
        legend=dict(x=1, xanchor="right", y=1, yanchor="top"),
    )

    save_figure(fig, output_path)


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "graphs"

    # Find all repo data directories
    repo_dirs = []
    for entry in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "issues.json")):
            repo_dirs.append(full)

    # Compute timelines
    all_timelines = []
    for rd in repo_dirs:
        tl = compute_open_issues_timeline(rd, day_range=(-90, 90))
        if tl:
            all_timelines.append(tl)
            print(f"  {tl['repo']}: {tl['open_at_adoption']} open at adoption, "
                  f"now {tl['normalized'][-1]:.0f}%")

    # Load bottleneck data if available
    bottleneck_path = os.path.join(os.path.dirname(data_dir) if data_dir != "data" else ".",
                                    "bottleneck-analysis.json")
    bottleneck_data = None
    if os.path.exists(bottleneck_path):
        bottleneck_data = load_json(bottleneck_path)

    # Generate graph
    os.makedirs(output_dir, exist_ok=True)
    generate_graph(all_timelines, os.path.join(output_dir, "normalized-open-issues.png"),
                   bottleneck_data)


if __name__ == "__main__":
    main()
