#!/usr/bin/env python3
"""
Analyze repo-assist workflow invocation rates over time, broken down by trigger type.

Three invocation categories:
  - Automated (scheduled): Automated scheduled runs (the factory's own clock)
  - Automated (additional): Manual dispatch from the GitHub Actions UI — the
                    maintainer dialing up the rate of automation.
  - Human intervention (/repo-assist): Event-triggered runs that actually
                    executed — issue comments, PR review comments, issue events,
                    PR events. These represent actual /repo-assist invocations
                    that passed pre-activation.

Filtering: Runs with conclusion 'skipped', 'cancelled', or 'action_required'
are excluded. Skipped runs are trigger firings (e.g. issue_comment events)
where the pre-activation check found no /repo-assist command. Action_required
runs are trigger firings waiting for approval that never executed.

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


# Conclusions that indicate the run never actually executed
EXCLUDED_CONCLUSIONS = ("skipped", "cancelled", "action_required")


def categorize_event(event):
    """Categorize a workflow event into one of three buckets."""
    if event == "schedule":
        return "scheduled"
    elif event == "workflow_dispatch":
        return "extra"
    else:
        # issue_comment, pull_request_review_comment, issues, pull_request,
        # discussion_comment, discussion — all event-driven /repo-assist runs
        return "repo-assist"


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

    # Filter out runs that never actually executed:
    # - skipped: pre-activation check found no /repo-assist command
    # - cancelled: run was cancelled before completion
    # - action_required: run was waiting for approval and never executed
    active_runs = [r for r in parsed_runs if r["conclusion"] not in EXCLUDED_CONCLUSIONS]
    excluded_count = len(parsed_runs) - len(active_runs)

    first_run = parsed_runs[0]["date"]
    last_run = parsed_runs[-1]["date"]
    total_days = max((last_run - first_run).days, 1)
    total_weeks = max(total_days / 7, 1)

    # Count by the three categories (active runs only)
    scheduled = sum(1 for r in active_runs if categorize_event(r["event"]) == "scheduled")
    repo_assist = sum(1 for r in active_runs if categorize_event(r["event"]) == "repo-assist")
    extra = sum(1 for r in active_runs if categorize_event(r["event"]) == "extra")

    # Keep detailed trigger counts for reference
    trigger_counts = defaultdict(int)
    for run in active_runs:
        trigger_counts[run["event"]] += 1

    # Success/failure counts (of active runs)
    successes = sum(1 for r in active_runs if r["conclusion"] == "success")
    failures = sum(1 for r in active_runs if r["conclusion"] == "failure")

    # Weekly time series by category (active runs only)
    weekly_scheduled = defaultdict(int)
    weekly_repo_assist = defaultdict(int)
    weekly_extra = defaultdict(int)

    for run in active_runs:
        week_start = first_run + timedelta(weeks=((run["date"] - first_run).days // 7))
        week_key = week_start.strftime("%Y-%m-%d")

        cat = categorize_event(run["event"])
        if cat == "scheduled":
            weekly_scheduled[week_key] += 1
        elif cat == "repo-assist":
            weekly_repo_assist[week_key] += 1
        else:
            weekly_extra[week_key] += 1

    return {
        "repo": repo_name,
        "total_runs": len(parsed_runs),
        "active_runs": len(active_runs),
        "excluded_runs": excluded_count,
        "first_run": first_run.strftime("%Y-%m-%d"),
        "last_run": last_run.strftime("%Y-%m-%d"),
        "total_days": total_days,
        "runs_per_day": round(len(active_runs) / total_days, 2),
        "runs_per_week": round(len(active_runs) / total_weeks, 2),
        "trigger_counts": dict(trigger_counts),
        "scheduled_runs": scheduled,
        "repo_assist_runs": repo_assist,
        "extra_runs": extra,
        "repo_assist_ratio": round(repo_assist / len(active_runs), 3) if active_runs else 0,
        "successes": successes,
        "failures": failures,
        "success_rate": round(successes / len(active_runs), 3) if active_runs else 0,
        # For graphing
        "_parsed_runs": parsed_runs,
        "_active_runs": active_runs,
        "_weekly_scheduled": dict(weekly_scheduled),
        "_weekly_repo_assist": dict(weekly_repo_assist),
        "_weekly_extra": dict(weekly_extra),
    }


def generate_invocation_graphs(all_results, output_dir):
    """Generate invocation rate graphs."""
    os.makedirs(output_dir, exist_ok=True)
    results = [r for r in all_results if r is not None]

    # === Graph 1: Runs/week by repo, stacked by 3 categories ===
    fig, ax = plt.subplots(figsize=(14, 7))
    results_sorted = sorted(results, key=lambda r: r["runs_per_week"], reverse=True)
    repos = [r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"] for r in results_sorted]
    x = np.arange(len(repos))

    sched_rates = [r["scheduled_runs"] / max(r["total_days"] / 7, 1) for r in results_sorted]
    extra_rates = [r["extra_runs"] / max(r["total_days"] / 7, 1) for r in results_sorted]
    ra_rates = [r["repo_assist_runs"] / max(r["total_days"] / 7, 1) for r in results_sorted]

    ax.bar(x, sched_rates, label="Automated (scheduled)", color="#1565C0")
    ax.bar(x, extra_rates, bottom=sched_rates,
           label="Automated (additional)", color="#64B5F6")
    ax.bar(x, ra_rates, bottom=[s + e for s, e in zip(sched_rates, extra_rates)],
           label="Human intervention (/repo-assist)", color="#4CAF50")

    # Add human intervention ratio labels
    for i, r in enumerate(results_sorted):
        total = sched_rates[i] + extra_rates[i] + ra_rates[i]
        if total > 0:
            ax.text(i, total + 0.3, f"{r['repo_assist_ratio']:.0%}",
                    ha="center", va="bottom", fontsize=8, color="#2E7D32")

    ax.set_xlabel("Repository")
    ax.set_ylabel("Workflow Runs per Week")
    ax.set_title("Repo Assist Invocation Rate by Category\n"
                 "(% = human intervention rate)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "invocation-rate-by-type.png"), dpi=150)
    plt.close(fig)

    # === Graph 2: Total runs by 3 categories per repo ===
    fig, ax = plt.subplots(figsize=(14, 7))

    sched_vals = [r["scheduled_runs"] for r in results_sorted]
    extra_vals = [r["extra_runs"] for r in results_sorted]
    ra_vals = [r["repo_assist_runs"] for r in results_sorted]

    ax.bar(x, sched_vals, label="Automated (scheduled)", color="#1565C0")
    ax.bar(x, extra_vals, bottom=sched_vals, label="Automated (additional)", color="#64B5F6")
    ax.bar(x, ra_vals, bottom=[s + e for s, e in zip(sched_vals, extra_vals)],
           label="Human intervention (/repo-assist)", color="#4CAF50")

    ax.set_xlabel("Repository")
    ax.set_ylabel("Total Active Workflow Runs")
    ax.set_title("Repo Assist Workflow Runs by Category (Total)")
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
        runs = r["_active_runs"]
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

    # === Graph 4: /repo-assist rate vs throughput (scatter) ===
    # Load bottleneck data if available
    bottleneck_path = os.path.join(os.path.dirname(output_dir), "bottleneck-analysis.json")
    if os.path.exists(bottleneck_path):
        bottleneck_data = load_json(bottleneck_path)
        bn_map = {b["repo"]: b for b in bottleneck_data}

        fig, ax = plt.subplots(figsize=(10, 8))
        status_colors = {
            "BLOCKED": "#D32F2F",
            "FLOWING": "#4CAF50",
            "IDLE": "#90CAF9",
        }

        for r in results:
            bn = bn_map.get(r["repo"])
            if not bn:
                continue
            color = status_colors.get(bn["bottleneck_status"], "#9E9E9E")
            ax.scatter(r["repo_assist_ratio"] * 100, bn["throughput_ratio"] * 100,
                       c=color, s=200, edgecolors="black", linewidth=0.5, zorder=5)
            label = r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"]
            ax.annotate(label, (r["repo_assist_ratio"] * 100, bn["throughput_ratio"] * 100),
                        textcoords="offset points", xytext=(8, 5), fontsize=9)

        ax.set_xlabel("Human Intervention Rate (% of active runs)")
        ax.set_ylabel("Pipeline Throughput (% of RA PRs merged)")
        ax.set_title("Human Intervention Rate vs Pipeline Throughput\n"
                     "(Red=BLOCKED, Green=FLOWING, Blue=IDLE)")
        ax.grid(True, alpha=0.3)
        ax.set_xlim(-5, 105)
        ax.set_ylim(-5, 105)
        fig.tight_layout()
        fig.savefig(os.path.join(output_dir, "invocation-vs-throughput.png"), dpi=150)
        plt.close(fig)


def print_summary(all_results):
    results = [r for r in all_results if r is not None]
    results.sort(key=lambda r: r["runs_per_week"], reverse=True)

    print(f"\n{'='*120}")
    print("REPO-ASSIST INVOCATION ANALYSIS (excluding skipped/cancelled/action_required runs)")
    print(f"{'='*120}")
    print(f"\n{'Repository':<35} {'Total':>6} {'Active':>7} {'Runs/wk':>8} {'A(sched)':>8} {'A(addl)':>7} "
          f"{'Human':>6} {'Hum%':>5} {'Succ%':>6}")
    print("-" * 100)

    for r in results:
        print(f"{r['repo']:<35} {r['total_runs']:>6} {r['active_runs']:>7} {r['runs_per_week']:>8.1f} "
              f"{r['scheduled_runs']:>8} {r['extra_runs']:>7} "
              f"{r['repo_assist_runs']:>6} "
              f"{r['repo_assist_ratio']*100:>4.0f}% "
              f"{r['success_rate']*100:>5.0f}%")

    print()
    total_runs = sum(r["total_runs"] for r in results)
    total_active = sum(r["active_runs"] for r in results)
    total_sched = sum(r["scheduled_runs"] for r in results)
    total_ra = sum(r["repo_assist_runs"] for r in results)
    total_extra = sum(r["extra_runs"] for r in results)
    total_excluded = sum(r["excluded_runs"] for r in results)
    print(f"Total: {total_runs} runs, {total_excluded} excluded ({total_excluded/total_runs*100:.0f}%), "
          f"{total_active} active "
          f"({total_sched} auto-scheduled, {total_extra} auto-additional, {total_ra} human)")
    print(f"  Automated (scheduled): {total_sched/total_active*100:.0f}%, "
          f"Automated (additional): {total_extra/total_active*100:.0f}%, "
          f"Human intervention: {total_ra/total_active*100:.0f}%")


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
                  f"{result['repo_assist_ratio']:.0%} /repo-assist")

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
