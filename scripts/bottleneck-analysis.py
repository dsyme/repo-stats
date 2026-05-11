#!/usr/bin/env python3
"""
Pipeline Bottleneck Analysis for repo-assist repositories.

Models each repository as a multi-stage "software factory" and applies
Theory of Constraints / Little's Law analysis to identify where the
pipeline is blocked.

Pipeline stages:
  1. Issue Backlog     — open issues waiting to be addressed
  2. PR Generation     — repo-assist creates PRs (automated, ~weekly)
  3. PR Review Queue   — PRs waiting for human review/merge (WIP)
  4. PR Merge          — human merges PR
  5. Issue Resolution  — issues get closed (via merge or triage)

Bottleneck identification uses:
  - Little's Law:  L = λ × W  (WIP = arrival rate × cycle time)
  - Throughput ratio: merge rate / creation rate (< 1 means accumulation)
  - WIP accumulation: open PRs as fraction of total created
  - Cycle time distribution: how long PRs sit in review queue

Usage: python3 bottleneck-analysis.py DATA_DIR [--output OUTPUT_DIR]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
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


def detect_repo_assist_adoption(data_dir):
    """Detect repo-assist adoption date."""
    pulls = load_json(os.path.join(data_dir, "pulls.json"))
    issues_raw = load_json(os.path.join(data_dir, "issues-raw.json"))

    ra_dates = []
    for pr in pulls:
        title = pr.get("title", "")
        labels = [l.get("name", "") for l in pr.get("labels", [])]
        if "[repo-assist]" in title.lower() or "[repo-assist]" in title or "repo-assist" in labels:
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


def analyze_pipeline(data_dir):
    """Perform full pipeline bottleneck analysis for a single repo."""
    meta = load_json(os.path.join(data_dir, "metadata.json"))
    pulls = load_json(os.path.join(data_dir, "pulls.json"))
    issues = load_json(os.path.join(data_dir, "issues.json"))
    issues_raw = load_json(os.path.join(data_dir, "issues-raw.json"))
    events = load_json(os.path.join(data_dir, "issue-events.json"))

    repo_name = meta.get("repo", os.path.basename(data_dir))
    now = datetime.now(timezone.utc)
    adoption = detect_repo_assist_adoption(data_dir)

    if not adoption:
        return None

    # ===== Stage 1: Identify repo-assist PRs =====
    ra_prs = []
    for pr in pulls:
        title = pr.get("title", "")
        labels = [l.get("name", "") for l in pr.get("labels", [])]
        if "[repo-assist]" in title or "[Repo Assist]" in title or "repo-assist" in labels:
            ra_prs.append(pr)

    # Classify RA PRs by state
    ra_merged = []
    ra_open = []
    ra_closed_unmerged = []

    for pr in ra_prs:
        merged_at = parse_dt(pr.get("merged_at"))
        closed_at = parse_dt(pr.get("closed_at"))
        state = pr.get("state", "")

        if merged_at:
            ra_merged.append(pr)
        elif state == "open":
            ra_open.append(pr)
        else:
            ra_closed_unmerged.append(pr)

    # ===== Stage 2: Compute pipeline metrics =====
    days_since_adoption = (now - adoption).days
    weeks_since_adoption = max(days_since_adoption / 7, 1)

    # PR Generation rate (automated stage)
    pr_creation_rate = len(ra_prs) / weeks_since_adoption

    # PR Merge rate (human stage)
    pr_merge_rate = len(ra_merged) / weeks_since_adoption

    # Throughput ratio: merge/creation (1.0 = balanced, <1 = bottleneck)
    throughput_ratio = len(ra_merged) / len(ra_prs) if ra_prs else 0

    # WIP at review stage: open PRs as fraction of total
    wip_count = len(ra_open)
    wip_fraction = wip_count / len(ra_prs) if ra_prs else 0

    # ===== Stage 3: Cycle time analysis =====
    # For merged PRs: time from creation to merge
    merge_cycle_times = []
    for pr in ra_merged:
        created = parse_dt(pr["created_at"])
        merged = parse_dt(pr["merged_at"])
        if created and merged:
            delta = (merged - created).total_seconds() / 86400  # days
            merge_cycle_times.append(delta)

    # For open PRs: time waiting so far (current age)
    open_wait_times = []
    for pr in ra_open:
        created = parse_dt(pr["created_at"])
        if created:
            delta = (now - created).total_seconds() / 86400  # days
            open_wait_times.append(delta)

    # For closed-unmerged PRs: time from creation to close
    rejected_cycle_times = []
    for pr in ra_closed_unmerged:
        created = parse_dt(pr["created_at"])
        closed = parse_dt(pr.get("closed_at"))
        if created and closed:
            delta = (closed - created).total_seconds() / 86400
            rejected_cycle_times.append(delta)

    # ===== Stage 4: Issue resolution analysis =====
    # How many issues were closed after adoption?
    issues_closed_after = 0
    issues_open_at_adoption = 0
    for issue in issues:
        created = parse_dt(issue["created_at"])
        closed = parse_dt(issue.get("closed_at"))
        if created and created <= adoption:
            if closed is None or closed > adoption:
                issues_open_at_adoption += 1
        if closed and closed > adoption:
            issues_closed_after += 1

    issues_open_now = sum(1 for i in issues if i.get("state") == "open")

    # ===== Stage 5: Little's Law analysis =====
    # Little's Law: L = λ × W
    # L = average WIP (open PRs)
    # λ = arrival rate (PR creation rate per day)
    # W = average time in system (cycle time)
    #
    # If the system is stable, W = L / λ
    # If W is growing, the bottleneck is at the review stage

    lambda_arrival = len(ra_prs) / max(days_since_adoption, 1)  # PRs per day
    lambda_departure = len(ra_merged) / max(days_since_adoption, 1)  # merges per day

    # Utilization: departure rate / arrival rate
    utilization = lambda_departure / lambda_arrival if lambda_arrival > 0 else 0

    # Average cycle time for merged PRs
    avg_merge_cycle = np.mean(merge_cycle_times) if merge_cycle_times else None
    median_merge_cycle = np.median(merge_cycle_times) if merge_cycle_times else None

    # Average wait time for still-open PRs
    avg_open_wait = np.mean(open_wait_times) if open_wait_times else None
    median_open_wait = np.median(open_wait_times) if open_wait_times else None

    # ===== Stage 6: Bottleneck classification =====
    # Distinguish three bottleneck types:
    #   A. INACTION: PRs sitting unreviewed (high WIP, low action)
    #   B. REJECTION: PRs actively reviewed but rejected (high rejection rate)
    #   C. BALANCED: pipeline flowing well

    rejection_rate = len(ra_closed_unmerged) / len(ra_prs) if ra_prs else 0
    action_rate = (len(ra_merged) + len(ra_closed_unmerged)) / len(ra_prs) if ra_prs else 0

    bottleneck_score = 0  # 0 = no bottleneck, higher = worse
    bottleneck_reasons = []

    if throughput_ratio < 0.5:
        bottleneck_score += 3
        bottleneck_reasons.append(f"Low merge rate: only {throughput_ratio:.0%} of RA PRs merged")
    elif throughput_ratio < 0.75:
        bottleneck_score += 1
        bottleneck_reasons.append(f"Moderate merge rate: {throughput_ratio:.0%} of RA PRs merged")

    if wip_fraction > 0.5:
        bottleneck_score += 3
        bottleneck_reasons.append(f"High WIP: {wip_fraction:.0%} of RA PRs still in review queue")
    elif wip_fraction > 0.25:
        bottleneck_score += 1
        bottleneck_reasons.append(f"Moderate WIP: {wip_fraction:.0%} of RA PRs in queue")

    if avg_open_wait and avg_merge_cycle and avg_open_wait > avg_merge_cycle * 2:
        bottleneck_score += 2
        bottleneck_reasons.append(
            f"Queue stall: open PRs waiting {avg_open_wait:.1f}d avg vs "
            f"{avg_merge_cycle:.1f}d avg merge cycle"
        )

    if avg_open_wait and avg_open_wait > 14:
        bottleneck_score += 2
        bottleneck_reasons.append(f"Long queue time: open PRs waiting {avg_open_wait:.1f}d average")

    if rejection_rate > 0.4:
        bottleneck_score += 2
        bottleneck_reasons.append(
            f"High rejection rate: {rejection_rate:.0%} of RA PRs closed without merge "
            f"({len(ra_closed_unmerged)} rejected)"
        )

    # Determine bottleneck *type*
    # Inaction: high WIP fraction, low action rate (PRs sitting unreviewed)
    # Rejection: low WIP but high rejection rate (maintainers reviewing but rejecting)
    # Mixed: both accumulation and rejection
    if wip_fraction > 0.4 and rejection_rate < 0.2:
        bottleneck_type = "INACTION"
        bottleneck_detail = (
            f"Pipeline blocked on human review: {wip_count} PRs awaiting action. "
            f"Repo-assist is producing work but maintainers are not reviewing/merging."
        )
    elif rejection_rate > 0.3 and wip_fraction < 0.15:
        bottleneck_type = "REJECTION"
        bottleneck_detail = (
            f"Maintainers are actively reviewing but rejecting {rejection_rate:.0%} of PRs "
            f"({len(ra_closed_unmerged)}/{len(ra_prs)}). This suggests either PR quality "
            f"issues or that the codebase requires domain expertise the automated workflow lacks."
        )
    elif wip_fraction > 0.2 and rejection_rate > 0.1:
        bottleneck_type = "MIXED"
        bottleneck_detail = (
            f"Both accumulation ({wip_count} open PRs) and rejection "
            f"({len(ra_closed_unmerged)} rejected). Partial maintainer engagement."
        )
    else:
        bottleneck_type = "NONE"
        bottleneck_detail = "Pipeline is flowing well."

    # Classify bottleneck severity
    if bottleneck_score >= 5:
        bottleneck_status = "BLOCKED"
        bottleneck_stage = "PR Review/Merge (human action required)"
    elif bottleneck_score >= 3:
        bottleneck_status = "CONSTRAINED"
        bottleneck_stage = "PR Review/Merge"
    elif bottleneck_score >= 1:
        bottleneck_status = "MINOR"
        bottleneck_stage = "PR Review/Merge"
    else:
        bottleneck_status = "FLOWING"
        bottleneck_stage = "None — pipeline balanced"

    return {
        "repo": repo_name,
        "adoption_date": adoption.strftime("%Y-%m-%d"),
        "days_since_adoption": days_since_adoption,
        "weeks_since_adoption": round(weeks_since_adoption, 1),

        # Pipeline inventory
        "ra_prs_total": len(ra_prs),
        "ra_prs_merged": len(ra_merged),
        "ra_prs_open": len(ra_open),
        "ra_prs_closed_unmerged": len(ra_closed_unmerged),

        # Flow rates
        "pr_creation_rate_per_week": round(pr_creation_rate, 2),
        "pr_merge_rate_per_week": round(pr_merge_rate, 2),
        "throughput_ratio": round(throughput_ratio, 3),
        "utilization": round(utilization, 3),

        # WIP
        "wip_count": wip_count,
        "wip_fraction": round(wip_fraction, 3),

        # Cycle times (days)
        "merge_cycle_time_avg": round(avg_merge_cycle, 1) if avg_merge_cycle is not None else None,
        "merge_cycle_time_median": round(median_merge_cycle, 1) if median_merge_cycle is not None else None,
        "merge_cycle_times": [round(t, 1) for t in merge_cycle_times],
        "open_wait_time_avg": round(avg_open_wait, 1) if avg_open_wait is not None else None,
        "open_wait_time_median": round(median_open_wait, 1) if median_open_wait is not None else None,
        "open_wait_times": [round(t, 1) for t in sorted(open_wait_times)],

        # Issue context
        "issues_open_at_adoption": issues_open_at_adoption,
        "issues_open_now": issues_open_now,
        "issues_closed_after_adoption": issues_closed_after,

        # Rejection analysis
        "rejection_rate": round(rejection_rate, 3),
        "action_rate": round(action_rate, 3),

        # Bottleneck assessment
        "bottleneck_score": bottleneck_score,
        "bottleneck_status": bottleneck_status,
        "bottleneck_type": bottleneck_type,
        "bottleneck_stage": bottleneck_stage,
        "bottleneck_reasons": bottleneck_reasons,
        "bottleneck_detail": bottleneck_detail,

        # Little's Law
        "littles_law": {
            "arrival_rate_per_day": round(lambda_arrival, 3),
            "departure_rate_per_day": round(lambda_departure, 3),
            "wip": wip_count,
            "implied_cycle_time_days": round(wip_count / lambda_arrival, 1) if lambda_arrival > 0 else None,
        },
    }


def generate_bottleneck_graphs(all_results, output_dir):
    """Generate comparative bottleneck visualization graphs."""
    os.makedirs(output_dir, exist_ok=True)

    results = [r for r in all_results if r is not None]
    results.sort(key=lambda r: r["throughput_ratio"])

    repos = [r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"] for r in results]
    x = np.arange(len(repos))

    # Color by bottleneck status
    status_colors = {
        "BLOCKED": "#D32F2F",
        "CONSTRAINED": "#FF9800",
        "MINOR": "#FFC107",
        "FLOWING": "#4CAF50",
    }
    colors = [status_colors.get(r["bottleneck_status"], "#9E9E9E") for r in results]

    # === Graph 1: Pipeline Flow Diagram (stacked bar) ===
    fig, ax = plt.subplots(figsize=(14, 7))
    merged = [r["ra_prs_merged"] for r in results]
    still_open = [r["ra_prs_open"] for r in results]
    closed_unmerged = [r["ra_prs_closed_unmerged"] for r in results]

    bars1 = ax.bar(x, merged, label="Merged (throughput)", color="#4CAF50")
    bars2 = ax.bar(x, still_open, bottom=merged, label="Open — awaiting review (WIP)", color="#FF9800")
    bottoms = [m + o for m, o in zip(merged, still_open)]
    bars3 = ax.bar(x, closed_unmerged, bottom=bottoms, label="Closed unmerged (rejected)", color="#9E9E9E")

    # Add throughput ratio labels
    for i, r in enumerate(results):
        total = r["ra_prs_total"]
        ratio = r["throughput_ratio"]
        ax.text(i, total + 1, f"{ratio:.0%}", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=colors[i])

    ax.set_xlabel("Repository")
    ax.set_ylabel("Repo-Assist PRs")
    ax.set_title("Pipeline Flow: Repo-Assist PR Disposition\n(% = throughput ratio: merged / created)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bottleneck-pipeline-flow.png"), dpi=150)
    plt.close(fig)

    # === Graph 2: Throughput ratio with bottleneck status ===
    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(x, [r["throughput_ratio"] * 100 for r in results], color=colors)
    ax.axhline(y=75, color="#4CAF50", linestyle="--", alpha=0.5, label="Healthy threshold (75%)")
    ax.axhline(y=50, color="#FF9800", linestyle="--", alpha=0.5, label="Warning threshold (50%)")
    ax.set_xlabel("Repository")
    ax.set_ylabel("Throughput Ratio (%)")
    ax.set_title("Pipeline Throughput Ratio: PR Merge Rate / PR Creation Rate\n"
                 "(Red = BLOCKED, Orange = CONSTRAINED, Yellow = MINOR, Green = FLOWING)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bottleneck-throughput-ratio.png"), dpi=150)
    plt.close(fig)

    # === Graph 3: Cycle Time Comparison (merged vs waiting) ===
    fig, ax = plt.subplots(figsize=(14, 6))
    merge_times = [r["merge_cycle_time_avg"] or 0 for r in results]
    wait_times = [r["open_wait_time_avg"] or 0 for r in results]
    w = 0.35
    ax.bar(x - w/2, merge_times, w, label="Avg merge cycle time (completed)", color="#4CAF50")
    ax.bar(x + w/2, wait_times, w, label="Avg wait time (still open)", color="#FF9800")
    ax.set_xlabel("Repository")
    ax.set_ylabel("Days")
    ax.set_title("Cycle Time: Merged PRs vs Still-Waiting PRs\n(Orange >> Green indicates review bottleneck)")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bottleneck-cycle-times.png"), dpi=150)
    plt.close(fig)

    # === Graph 4: WIP Accumulation ===
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x, [r["wip_count"] for r in results], color=colors)
    ax.set_xlabel("Repository")
    ax.set_ylabel("Open Repo-Assist PRs (WIP)")
    ax.set_title("Work-In-Progress: Repo-Assist PRs Awaiting Human Review")
    ax.set_xticks(x)
    ax.set_xticklabels(repos, rotation=45, ha="right")
    ax.grid(True, alpha=0.3, axis="y")
    # Add status labels
    for i, r in enumerate(results):
        if r["wip_count"] > 0:
            ax.text(i, r["wip_count"] + 0.3, r["bottleneck_status"],
                    ha="center", va="bottom", fontsize=8, fontweight="bold", color=colors[i])
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bottleneck-wip.png"), dpi=150)
    plt.close(fig)

    # === Graph 5: Bottleneck Impact — throughput ratio vs backlog clearance ===
    fig, ax = plt.subplots(figsize=(10, 8))
    throughputs = [r["throughput_ratio"] * 100 for r in results]
    # Backlog clearance
    clearances = []
    for r in results:
        oaa = r["issues_open_at_adoption"]
        closed = r["issues_closed_after_adoption"]
        clearances.append(min(closed / oaa * 100, 100) if oaa > 0 else 0)

    scatter = ax.scatter(throughputs, clearances, c=colors, s=200, edgecolors="black", linewidth=0.5, zorder=5)
    for i, r in enumerate(results):
        label = r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"]
        ax.annotate(label, (throughputs[i], clearances[i]),
                    textcoords="offset points", xytext=(8, 5), fontsize=9)

    ax.set_xlabel("Pipeline Throughput Ratio (% of RA PRs merged)")
    ax.set_ylabel("Backlog Clearance (%)")
    ax.set_title("Bottleneck Impact: Pipeline Throughput vs Backlog Clearance\n"
                 "(repos in bottom-left have blocked pipelines → low clearance)")
    ax.axvline(x=50, color="#FF9800", linestyle="--", alpha=0.4)
    ax.axvline(x=75, color="#4CAF50", linestyle="--", alpha=0.4)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "bottleneck-impact-scatter.png"), dpi=150)
    plt.close(fig)


def print_summary(all_results):
    """Print a text summary of the bottleneck analysis."""
    results = [r for r in all_results if r is not None]
    results.sort(key=lambda r: r["throughput_ratio"])

    print("\n" + "=" * 100)
    print("PIPELINE BOTTLENECK ANALYSIS — REPO-ASSIST REPOSITORIES")
    print("=" * 100)
    print()
    print(f"\n{'Repository':<35} {'Status':<12} {'Type':<10} {'RA PRs':>7} {'Merged':>7} {'Reject':>7} {'Open':>5} "
          f"{'Thru%':>6} {'Rej%':>5} {'WIP%':>5} {'MergeCT':>8} {'WaitCT':>8}")
    print("-" * 120)

    for r in results:
        repo = r["repo"]
        print(f"{repo:<35} {r['bottleneck_status']:<12} {r['bottleneck_type']:<10} "
              f"{r['ra_prs_total']:>7} "
              f"{r['ra_prs_merged']:>7} {r['ra_prs_closed_unmerged']:>7} {r['ra_prs_open']:>5} "
              f"{r['throughput_ratio']*100:>5.0f}% {r['rejection_rate']*100:>4.0f}% "
              f"{r['wip_fraction']*100:>4.0f}% "
              f"{r['merge_cycle_time_avg'] or 0:>7.1f}d "
              f"{r['open_wait_time_avg'] or 0:>7.1f}d")

    print()
    print("BOTTLENECK DETAILS:")
    print("-" * 120)
    for r in results:
        if r["bottleneck_status"] != "FLOWING":
            print(f"\n  {r['repo']} [{r['bottleneck_status']}] — type: {r['bottleneck_type']}:")
            print(f"    Summary: {r['bottleneck_detail']}")
            for reason in r["bottleneck_reasons"]:
                print(f"    • {reason}")
            ll = r["littles_law"]
            print(f"    Little's Law: λ_in={ll['arrival_rate_per_day']:.3f}/day, "
                  f"λ_out={ll['departure_rate_per_day']:.3f}/day, "
                  f"WIP={ll['wip']}, "
                  f"implied cycle time={ll['implied_cycle_time_days']}d")


def main():
    parser = argparse.ArgumentParser(description="Pipeline bottleneck analysis for repo-assist repos")
    parser.add_argument("data_dir", help="Root data directory containing per-repo subdirs")
    parser.add_argument("--output", default="graphs", help="Output directory for graphs")
    args = parser.parse_args()

    data_dir = args.data_dir
    output_dir = args.output

    # Find all repo data directories
    repo_dirs = []
    for entry in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "pulls.json")):
            repo_dirs.append(full)

    print(f"Found {len(repo_dirs)} repositories in {data_dir}")

    all_results = []
    for rd in repo_dirs:
        result = analyze_pipeline(rd)
        if result:
            all_results.append(result)
            print(f"  ✓ {result['repo']}: {result['bottleneck_status']} "
                  f"(throughput={result['throughput_ratio']:.0%}, "
                  f"WIP={result['ra_prs_open']})")
        else:
            print(f"  ✗ {os.path.basename(rd)}: no repo-assist detected")

    # Print summary
    print_summary(all_results)

    # Generate graphs
    generate_bottleneck_graphs(all_results, output_dir)
    print(f"\nGraphs saved to {output_dir}/bottleneck-*.png")

    # Save JSON results
    output_json = os.path.join(os.path.dirname(data_dir) if data_dir != "data" else ".",
                               "bottleneck-analysis.json")
    # Make serializable (remove raw cycle time lists for cleaner output, keep summaries)
    export = []
    for r in all_results:
        e = dict(r)
        # Keep cycle time lists for reference but they're already rounded
        export.append(e)

    with open(output_json, "w") as f:
        json.dump(export, f, indent=2)
    print(f"Analysis saved to {output_json}")


if __name__ == "__main__":
    main()
