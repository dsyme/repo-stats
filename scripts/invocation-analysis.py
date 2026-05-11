#!/usr/bin/env python3
"""
Analyze repo-assist workflow invocation rates over time, broken down by trigger type.

Trigger types and their meaning in the software factory model:
  - schedule:    Automated scheduled runs (the factory's own clock)
  - issue_comment:  Human "/repo-assist" comments (synchronous human intervention)
  - workflow_dispatch: Manual UI trigger (human-initiated batch runs)
  - issues:      Triggered by issue events (automated reaction)
  - pull_request / pull_request_review_comment: Triggered by PR events (automated reaction)

Usage: python3 invocation-analysis.py DATA_DIR [OUTPUT_DIR]
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np


def parse_dt(s):
    if s is None:
        return None
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


# Group triggers into meaningful categories
TRIGGER_CATEGORIES = {
    "schedule": "Scheduled (automated)",
    "issue_comment": "Issue comment (/repo-assist)",
    "workflow_dispatch": "Manual dispatch (UI)",
    "issues": "Issue event (automated)",
    "pull_request": "PR event (automated)",
    "pull_request_review_comment": "PR review comment",
    "discussion_comment": "Discussion comment",
    "discussion": "Discussion",
}

# Simplified grouping for the factory model
FACTORY_GROUPS = {
    "schedule": "automated",
    "issues": "automated",
    "pull_request": "automated",
    "issue_comment": "human-initiated",
    "workflow_dispatch": "human-initiated",
    "pull_request_review_comment": "human-initiated",
    "discussion_comment": "human-initiated",
    "discussion": "automated",
}


def analyze_repo_invocations(data_dir):
    """Analyze workflow invocation rates for a single repo."""
    meta = load_json(os.path.join(data_dir, "metadata.json"))
    wf_path = os.path.join(data_dir, "workflow-runs.json")
    if not os.path.exists(wf_path):
        return None

    runs = load_json(wf_path)
    if not runs:
        return None

    repo_name = meta.get("repo", os.path.basename(data_dir))

    # Parse all runs
    parsed_runs = []
    for run in runs:
        dt = parse_dt(run.get("created_at"))
        if dt:
            parsed_runs.append({
                "date": dt,
                "event": run.get("event", "unknown"),
                "conclusion": run.get("conclusion", "unknown"),
                "status": run.get("status", "unknown"),
            })

    parsed_runs.sort(key=lambda r: r["date"])

    if not parsed_runs:
        return None

    first_run = parsed_runs[0]["date"]
    last_run = parsed_runs[-1]["date"]
    total_days = max((last_run - first_run).days, 1)
    total_weeks = max(total_days / 7, 1)

    # Count by trigger type
    trigger_counts = defaultdict(int)
    for run in parsed_runs:
        trigger_counts[run["event"]] += 1

    # Count by factory group
    automated = sum(1 for r in parsed_runs if FACTORY_GROUPS.get(r["event"], "automated") == "automated")
    human_initiated = sum(1 for r in parsed_runs if FACTORY_GROUPS.get(r["event"], "automated") == "human-initiated")

    # Success/failure counts
    successes = sum(1 for r in parsed_runs if r["conclusion"] == "success")
    failures = sum(1 for r in parsed_runs if r["conclusion"] in ("failure", "cancelled"))
    skipped = sum(1 for r in parsed_runs if r["conclusion"] == "skipped")

    # Weekly time series by trigger group
    weekly_automated = defaultdict(int)
    weekly_human = defaultdict(int)
    weekly_total = defaultdict(int)

    for run in parsed_runs:
        # Week number relative to first run
        week_start = first_run + timedelta(weeks=((run["date"] - first_run).days // 7))
        week_key = week_start.strftime("%Y-%m-%d")

        group = FACTORY_GROUPS.get(run["event"], "automated")
        weekly_total[week_key] += 1
        if group == "automated":
            weekly_automated[week_key] += 1
        else:
            weekly_human[week_key] += 1

    # Daily time series for the graph (smoother)
    daily_by_trigger = defaultdict(lambda: defaultdict(int))
    for run in parsed_runs:
        day_key = run["date"].strftime("%Y-%m-%d")
        daily_by_trigger[run["event"]][day_key] += 1

    return {
        "repo": repo_name,
        "total_runs": len(parsed_runs),
        "first_run": first_run.strftime("%Y-%m-%d"),
        "last_run": last_run.strftime("%Y-%m-%d"),
        "total_days": total_days,
        "runs_per_day": round(len(parsed_runs) / total_days, 2),
        "runs_per_week": round(len(parsed_runs) / total_weeks, 2),
        "trigger_counts": dict(trigger_counts),
        "automated_runs": automated,
        "human_initiated_runs": human_initiated,
        "human_ratio": round(human_initiated / len(parsed_runs), 3) if parsed_runs else 0,
        "successes": successes,
        "failures": failures,
        "skipped": skipped,
        "success_rate": round(successes / len(parsed_runs), 3) if parsed_runs else 0,
        # For graphing
        "_parsed_runs": parsed_runs,
        "_weekly_automated": dict(weekly_automated),
        "_weekly_human": dict(weekly_human),
    }


def generate_invocation_graphs(all_results, output_dir):
    """Generate invocation rate graphs."""
    os.makedirs(output_dir, exist_ok=True)
    results = [r for r in all_results if r is not None]

    # === Graph 1: Runs/week by repo, stacked by automated vs human ===
    fig, ax = plt.subplots(figsize=(14, 7))
    results_sorted = sorted(results, key=lambda r: r["runs_per_week"], reverse=True)
    repos = [r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"] for r in results_sorted]
    x = np.arange(len(repos))

    auto_rates = [r["automated_runs"] / max(r["total_days"] / 7, 1) for r in results_sorted]
    human_rates = [r["human_initiated_runs"] / max(r["total_days"] / 7, 1) for r in results_sorted]

    bars1 = ax.bar(x, auto_rates, label="Automated (schedule, issue/PR events)", color="#2196F3")
    bars2 = ax.bar(x, human_rates, bottom=auto_rates,
                   label="Human-initiated (comments, dispatch)", color="#FF9800")

    # Add human ratio labels
    for i, r in enumerate(results_sorted):
        total = auto_rates[i] + human_rates[i]
        if total > 0:
            ax.text(i, total + 0.3, f"{r['human_ratio']:.0%}h",
                    ha="center", va="bottom", fontsize=8, color="#E65100")

    ax.set_xlabel("Repository")
    ax.set_ylabel("Workflow Runs per Week")
    ax.set_title("Repo-Assist Invocation Rate by Trigger Type\n"
                 "(% = proportion of human-initiated runs)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "invocation-rate-by-type.png"), dpi=150)
    plt.close(fig)

    # === Graph 2: Detailed trigger breakdown per repo ===
    fig, ax = plt.subplots(figsize=(14, 7))
    trigger_types = ["schedule", "issue_comment", "workflow_dispatch", "issues",
                     "pull_request", "pull_request_review_comment"]
    trigger_colors = {
        "schedule": "#2196F3",
        "issue_comment": "#FF9800",
        "workflow_dispatch": "#F44336",
        "issues": "#4CAF50",
        "pull_request": "#9C27B0",
        "pull_request_review_comment": "#FF5722",
    }
    trigger_labels = {
        "schedule": "Scheduled",
        "issue_comment": "/repo-assist comment",
        "workflow_dispatch": "Manual dispatch",
        "issues": "Issue event",
        "pull_request": "PR event",
        "pull_request_review_comment": "PR review comment",
    }

    bottoms = np.zeros(len(repos))
    for trigger in trigger_types:
        values = [r["trigger_counts"].get(trigger, 0) for r in results_sorted]
        ax.bar(x, values, bottom=bottoms,
               label=trigger_labels.get(trigger, trigger),
               color=trigger_colors.get(trigger, "#9E9E9E"))
        bottoms += np.array(values)

    ax.set_xlabel("Repository")
    ax.set_ylabel("Total Workflow Runs")
    ax.set_title("Repo-Assist Workflow Runs by Trigger Type (Total)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "invocation-trigger-breakdown.png"), dpi=150)
    plt.close(fig)

    # === Graph 3: Runs over time (7-day rolling avg), all repos overlaid ===
    fig, ax = plt.subplots(figsize=(14, 7))
    cmap = plt.cm.tab10

    for i, r in enumerate(results_sorted):
        runs = r["_parsed_runs"]
        if not runs:
            continue

        # Build daily counts
        first = runs[0]["date"].date()
        last = runs[-1]["date"].date()
        day_count = (last - first).days + 1
        if day_count < 7:
            continue

        daily = np.zeros(day_count)
        for run in runs:
            idx = (run["date"].date() - first).days
            if 0 <= idx < day_count:
                daily[idx] += 1

        # 7-day rolling average
        kernel = np.ones(7) / 7
        rolling = np.convolve(daily, kernel, mode="valid")
        dates = [first + timedelta(days=d + 3) for d in range(len(rolling))]

        repo_short = r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"]
        ax.plot(dates, rolling, label=repo_short,
                color=cmap(i / len(results_sorted)), linewidth=1.5, alpha=0.8)

    ax.set_xlabel("Date")
    ax.set_ylabel("Runs per Day (7-day rolling avg)")
    ax.set_title("Repo-Assist Activity Over Time (7-day rolling average)")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "invocation-over-time.png"), dpi=150)
    plt.close(fig)

    # === Graph 4: Human intervention rate vs throughput (scatter) ===
    # Load bottleneck data if available
    bottleneck_path = os.path.join(os.path.dirname(output_dir), "bottleneck-analysis.json")
    if os.path.exists(bottleneck_path):
        bottleneck_data = load_json(bottleneck_path)
        bn_map = {b["repo"]: b for b in bottleneck_data}

        fig, ax = plt.subplots(figsize=(10, 8))
        status_colors = {
            "BLOCKED": "#D32F2F",
            "CONSTRAINED": "#FF9800",
            "MINOR": "#FFC107",
            "FLOWING": "#4CAF50",
        }

        for r in results:
            bn = bn_map.get(r["repo"])
            if not bn:
                continue
            color = status_colors.get(bn["bottleneck_status"], "#9E9E9E")
            ax.scatter(r["human_ratio"] * 100, bn["throughput_ratio"] * 100,
                       c=color, s=200, edgecolors="black", linewidth=0.5, zorder=5)
            label = r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"]
            ax.annotate(label, (r["human_ratio"] * 100, bn["throughput_ratio"] * 100),
                        textcoords="offset points", xytext=(8, 5), fontsize=9)

        ax.set_xlabel("Human-Initiated Invocations (% of all runs)")
        ax.set_ylabel("Pipeline Throughput (% of RA PRs merged)")
        ax.set_title("Human Intervention Rate vs Pipeline Throughput\n"
                     "(Red=BLOCKED, Orange=CONSTRAINED, Yellow=MINOR, Green=FLOWING)")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "invocation-vs-throughput.png"), dpi=150)
        plt.close(fig)


def print_summary(all_results):
    results = [r for r in all_results if r is not None]
    results.sort(key=lambda r: r["runs_per_week"], reverse=True)

    print(f"\n{'='*110}")
    print("REPO-ASSIST INVOCATION ANALYSIS")
    print(f"{'='*110}")
    print(f"\n{'Repository':<35} {'Runs':>6} {'Runs/wk':>8} {'Auto':>6} {'Human':>6} "
          f"{'Hum%':>5} {'Sched':>6} {'Comment':>8} {'Dispatch':>9} {'Issue':>6} "
          f"{'PR':>4} {'Succ%':>6}")
    print("-" * 110)

    for r in results:
        tc = r["trigger_counts"]
        print(f"{r['repo']:<35} {r['total_runs']:>6} {r['runs_per_week']:>8.1f} "
              f"{r['automated_runs']:>6} {r['human_initiated_runs']:>6} "
              f"{r['human_ratio']*100:>4.0f}% "
              f"{tc.get('schedule', 0):>6} {tc.get('issue_comment', 0):>8} "
              f"{tc.get('workflow_dispatch', 0):>9} {tc.get('issues', 0):>6} "
              f"{tc.get('pull_request', 0):>4} "
              f"{r['success_rate']*100:>5.0f}%")

    print()
    total_runs = sum(r["total_runs"] for r in results)
    total_human = sum(r["human_initiated_runs"] for r in results)
    total_auto = sum(r["automated_runs"] for r in results)
    print(f"Total across all repos: {total_runs} runs "
          f"({total_auto} automated, {total_human} human-initiated, "
          f"{total_human/total_runs*100:.0f}% human)")


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "graphs"

    repo_dirs = []
    for entry in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "workflow-runs.json")):
            repo_dirs.append(full)

    print(f"Found {len(repo_dirs)} repositories with workflow run data")

    all_results = []
    for rd in repo_dirs:
        result = analyze_repo_invocations(rd)
        if result:
            all_results.append(result)
            print(f"  {result['repo']}: {result['total_runs']} runs, "
                  f"{result['runs_per_week']:.1f}/wk, "
                  f"{result['human_ratio']:.0%} human-initiated")

    print_summary(all_results)

    # Save JSON (without internal graphing data)
    export = []
    for r in all_results:
        e = {k: v for k, v in r.items() if not k.startswith("_")}
        export.append(e)

    output_json = os.path.join(os.path.dirname(data_dir) if data_dir != "data" else ".",
                               "invocation-analysis.json")
    with open(output_json, "w") as f:
        json.dump(export, f, indent=2)
    print(f"\nAnalysis saved to {output_json}")

    generate_invocation_graphs(all_results, output_dir)
    print(f"Graphs saved to {output_dir}/invocation-*.png")


if __name__ == "__main__":
    main()
