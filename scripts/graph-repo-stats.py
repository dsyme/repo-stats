#!/usr/bin/env python3
"""
Generic script to generate repository statistics graphs from downloaded GitHub data.

Usage: python3 graph-repo-stats.py [DATA_DIR] [--output OUTPUT_DIR] [--months N]

DATA_DIR defaults to ./github-data
OUTPUT_DIR defaults to DATA_DIR
--months N limits the time window to the last N months (default: 6)

Generates:
  - open-issues-over-time.png: Number of open issues at each point in time
  - merge-rate.png: PRs merged per week
  - pr-time-to-merge.png: How long PRs stay open before merge (rolling average)
  - issue-activity.png: Issues opened vs closed per week
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go

from chart_theme import make_figure, save_figure, add_adoption_line, COLORS, PALETTE


def parse_dt(s):
    """Parse ISO 8601 datetime string."""
    if s is None:
        return None
    # Handle both 'Z' suffix and '+00:00'
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def detect_adoption_date(data_dir):
    """Detect repo-assist adoption date from issues-raw.json and pulls.json."""
    ra_dates = []
    for fname in ("issues-raw.json", "pulls.json"):
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            continue
        for item in load_json(path):
            labels = [l.get("name", "") for l in item.get("labels", [])]
            title = item.get("title", "")
            if "repo-assist" in labels or "[repo-assist]" in title.lower() or "[Repo Assist]" in title:
                dt = parse_dt(item.get("created_at"))
                if dt:
                    ra_dates.append(dt)
    return min(ra_dates) if ra_dates else None


# ---------------------------------------------------------------------------
# Graph 1: Open issues over time
# ---------------------------------------------------------------------------
def graph_open_issues(issues, cutoff, output_path, repo_name="", adoption_date=None):
    """Reconstruct open issue count over time from created_at / closed_at."""
    events = []  # (datetime, delta)  delta = +1 for open, -1 for close
    for issue in issues:
        created = parse_dt(issue["created_at"])
        if created is None:
            continue
        events.append((created, +1))
        closed = parse_dt(issue.get("closed_at"))
        if closed is not None:
            events.append((closed, -1))

    events.sort(key=lambda x: x[0])

    # Build time series: sample daily
    if not events:
        print("  No issue data to plot.")
        return

    start = max(cutoff, events[0][0])
    end = datetime.now(timezone.utc)
    
    # First, compute the open count at `start` by replaying all events before it
    open_count = 0
    remaining_events = []
    for dt, delta in events:
        if dt < start:
            open_count += delta
        else:
            remaining_events.append((dt, delta))

    # Now walk day by day
    dates = []
    counts = []
    event_idx = 0
    day = start
    while day <= end:
        while event_idx < len(remaining_events) and remaining_events[event_idx][0] <= day:
            open_count += remaining_events[event_idx][1]
            event_idx += 1
        dates.append(day)
        counts.append(open_count)
        day += timedelta(days=1)

    title = f"{repo_name} — Open Issues Over Time" if repo_name else "Open Issues Over Time"
    fig = make_figure(title=title)
    fig.add_trace(go.Scatter(
        x=dates, y=counts,
        fill="tozeroy",
        line=dict(width=1.5, color=COLORS["primary"]),
        fillcolor="rgba(21, 101, 192, 0.3)",
        name="Open Issues",
    ))
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Open Issues")
    add_adoption_line(fig, adoption_date)
    save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Graph 2: Merge rate (PRs merged per week)
# ---------------------------------------------------------------------------
def graph_merge_rate(pulls, cutoff, output_path, repo_name="", adoption_date=None):
    merged_dates = []
    for pr in pulls:
        merged = parse_dt(pr.get("merged_at"))
        if merged and merged >= cutoff:
            merged_dates.append(merged)

    if not merged_dates:
        print("  No merged PR data to plot.")
        return

    merged_dates.sort()

    # Bucket by week (ISO week)
    weeks = defaultdict(int)
    for d in merged_dates:
        week_start = d - timedelta(days=d.weekday())
        week_key = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        weeks[week_key] += 1

    sorted_weeks = sorted(weeks.items())
    dates = [w[0] for w in sorted_weeks]
    counts = [w[1] for w in sorted_weeks]

    title = f"{repo_name} — PRs Merged Per Week" if repo_name else "PRs Merged Per Week"
    fig = make_figure(title=title)
    fig.add_trace(go.Bar(
        x=dates, y=counts,
        marker_color=COLORS["primary"],
        opacity=0.7,
        name="PRs Merged",
    ))
    fig.update_xaxes(title_text="Week starting")
    fig.update_yaxes(title_text="PRs Merged")
    add_adoption_line(fig, adoption_date)
    save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Graph 3: PR time-to-merge (rolling 10-PR average, in days)
# ---------------------------------------------------------------------------
def graph_pr_time_to_merge(pulls, cutoff, output_path, repo_name="", adoption_date=None):
    durations = []
    for pr in pulls:
        created = parse_dt(pr.get("created_at"))
        merged = parse_dt(pr.get("merged_at"))
        if created and merged and merged >= cutoff:
            days = (merged - created).total_seconds() / 86400
            durations.append((merged, days))

    if not durations:
        print("  No PR merge duration data to plot.")
        return

    durations.sort(key=lambda x: x[0])
    dates = [d[0] for d in durations]
    days_open = [d[1] for d in durations]

    # Rolling average
    window = min(10, len(days_open))
    rolling = []
    for i in range(len(days_open)):
        start = max(0, i - window + 1)
        rolling.append(sum(days_open[start:i+1]) / (i - start + 1))

    title = f"{repo_name} — PR Time to Merge (days)" if repo_name else "PR Time to Merge (days)"
    fig = make_figure(title=title)
    fig.add_trace(go.Scatter(
        x=dates, y=days_open,
        mode="markers",
        marker=dict(size=5, color=COLORS["primary"], opacity=0.3),
        name="Individual PRs",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=rolling,
        mode="lines",
        line=dict(width=2, color=COLORS["danger"]),
        name=f"Rolling avg ({window})",
    ))
    fig.update_xaxes(title_text="Merge Date")
    fig.update_yaxes(title_text="Days Open")
    add_adoption_line(fig, adoption_date)
    save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Graph 4: Issue open/close activity per week
# ---------------------------------------------------------------------------
def graph_issue_activity(issues, cutoff, output_path, repo_name="", adoption_date=None):
    opened_weeks = defaultdict(int)
    closed_weeks = defaultdict(int)

    for issue in issues:
        created = parse_dt(issue["created_at"])
        if created and created >= cutoff:
            week_start = created - timedelta(days=created.weekday())
            week_key = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            opened_weeks[week_key] += 1

        closed = parse_dt(issue.get("closed_at"))
        if closed and closed >= cutoff:
            week_start = closed - timedelta(days=closed.weekday())
            week_key = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            closed_weeks[week_key] += 1

    all_weeks = sorted(set(opened_weeks) | set(closed_weeks))
    if not all_weeks:
        print("  No issue activity data to plot.")
        return

    opened = [opened_weeks.get(w, 0) for w in all_weeks]
    closed = [closed_weeks.get(w, 0) for w in all_weeks]

    title = f"{repo_name} — Issue Activity Per Week (Opened vs Closed)" if repo_name else "Issue Activity Per Week (Opened vs Closed)"
    fig = make_figure(title=title)
    fig.add_trace(go.Bar(
        x=all_weeks, y=opened,
        name="Opened",
        marker_color=COLORS["danger"],
        opacity=0.7,
    ))
    fig.add_trace(go.Bar(
        x=all_weeks, y=closed,
        name="Closed",
        marker_color=COLORS["secondary"],
        opacity=0.7,
    ))
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Week starting")
    fig.update_yaxes(title_text="Count")
    add_adoption_line(fig, adoption_date)
    save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate repo stats graphs from GitHub data.")
    parser.add_argument("data_dir", nargs="?", default="./github-data", help="Directory with downloaded JSON data")
    parser.add_argument("--output", "-o", default=None, help="Output directory for graphs (default: same as data_dir)")
    parser.add_argument("--months", "-m", type=int, default=6, help="Number of months of history to show (default: 6)")
    args = parser.parse_args()

    data_dir = args.data_dir
    output_dir = args.output or data_dir
    os.makedirs(output_dir, exist_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.months * 30)

    # Load metadata for title
    meta_path = os.path.join(data_dir, "metadata.json")
    repo_name = "Repository"
    if os.path.exists(meta_path):
        meta = load_json(meta_path)
        repo_name = meta.get("repo", repo_name)

    print(f"Generating graphs for {repo_name} (last {args.months} months)")

    # Load data
    issues_path = os.path.join(data_dir, "issues.json")
    pulls_path = os.path.join(data_dir, "pulls.json")

    issues = load_json(issues_path) if os.path.exists(issues_path) else []
    pulls = load_json(pulls_path) if os.path.exists(pulls_path) else []

    print(f"Loaded {len(issues)} issues, {len(pulls)} PRs")

    # Detect repo-assist adoption date
    adoption_date = detect_adoption_date(data_dir)
    if adoption_date:
        print(f"Repo-assist adoption detected: {adoption_date.strftime('%Y-%m-%d')}")

    # Generate graphs
    print("Generating open issues over time...")
    graph_open_issues(issues, cutoff, os.path.join(output_dir, "open-issues-over-time.png"), repo_name, adoption_date)

    print("Generating merge rate...")
    graph_merge_rate(pulls, cutoff, os.path.join(output_dir, "merge-rate.png"), repo_name, adoption_date)

    print("Generating PR time to merge...")
    graph_pr_time_to_merge(pulls, cutoff, os.path.join(output_dir, "pr-time-to-merge.png"), repo_name, adoption_date)

    print("Generating issue activity...")
    graph_issue_activity(issues, cutoff, os.path.join(output_dir, "issue-activity.png"), repo_name, adoption_date)

    print("All graphs generated.")


if __name__ == "__main__":
    main()
