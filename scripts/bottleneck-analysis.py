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
import re
import sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import numpy as np
import plotly.graph_objects as go
from chart_theme import make_figure, save_figure, COLORS, PALETTE, STATUS_COLORS


def parse_dt(s):
    if s is None:
        return None
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def load_json_safe(path):
    if os.path.exists(path):
        return load_json(path)
    return []


def detect_repo_assist_adoption(data_dir):
    """Detect repo-assist adoption date."""
    pulls = load_json(os.path.join(data_dir, "pulls.json"))
    issues_raw = load_json_safe(os.path.join(data_dir, "issues-raw.json"))

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
    issues_raw = load_json_safe(os.path.join(data_dir, "issues-raw.json"))
    events = load_json_safe(os.path.join(data_dir, "issue-events.json"))

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

    # ===== Stage 1b: Identify comment-path (investigation) activity =====
    # Repo-assist has two output paths per issue:
    #   A. PR path: creates a PR to fix the issue
    #   B. Comment path: investigates and leaves a comment (e.g. "already fixed",
    #      "this is a question", triage note) — may lead to closure without a PR
    #
    # We detect the comment path by finding issues where github-actions[bot]
    # left a "Repo Assist" comment but did NOT create a PR.

    ra_pr_numbers = set(pr["number"] for pr in ra_prs)
    issue_map = {i["number"]: i for i in issues}

    comment_path_issues = set()
    comment_path_closed = set()
    comment_path_open = set()
    pr_path_issues = set()  # issues that received a PR-creation comment

    bot_comments_path = os.path.join(data_dir, "bot-comments.json")
    if os.path.exists(bot_comments_path):
        bot_comments = load_json(bot_comments_path)

        # Group bot comments by issue number
        comments_by_issue = defaultdict(list)
        for c in bot_comments:
            m = re.search(r"/issues/(\d+)$", c.get("issue_url", ""))
            if m:
                inum = int(m.group(1))
                comments_by_issue[inum].append(c)

        for inum, clist in comments_by_issue.items():
            if inum in ra_pr_numbers:
                continue  # This IS a PR, skip

            has_pr_mention = any(
                "Pull request created" in c["body"]
                or "created a draft PR" in c["body"]
                or "draft PR has been opened" in c["body"]
                for c in clist
            )
            has_ra_response = any(
                "automated response from Repo Assist" in c["body"]
                or "Repo Assist completed" in c["body"]
                for c in clist
            )

            if has_pr_mention:
                pr_path_issues.add(inum)
            elif has_ra_response:
                comment_path_issues.add(inum)
                if inum in issue_map:
                    if issue_map[inum]["state"] == "closed":
                        comment_path_closed.add(inum)
                    else:
                        comment_path_open.add(inum)

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
        bottleneck_status = "FLOWING"
        bottleneck_stage = "Minor friction but pipeline operating"
    elif bottleneck_score >= 1:
        bottleneck_status = "FLOWING"
        bottleneck_stage = "Minor friction but pipeline operating"
    else:
        bottleneck_status = "FLOWING"
        bottleneck_stage = "None — pipeline balanced"

    # Check for IDLE status: if WIP is very low AND open issues are very low,
    # the factory has effectively cleared its backlog and is waiting for new
    # work rather than being constrained. Override CONSTRAINED/MINOR → IDLE.
    idle_threshold_issues = 5  # fewer than this = effectively idle
    idle_threshold_wip = 2     # fewer open PRs than this
    is_idle = (issues_open_now <= idle_threshold_issues
               and wip_count <= idle_threshold_wip
               and bottleneck_status in ("CONSTRAINED", "MINOR", "FLOWING"))

    if is_idle:
        bottleneck_status = "IDLE"
        bottleneck_stage = "Input-starved — backlog cleared"
        bottleneck_type = "NONE"
        bottleneck_detail = (
            f"Factory effectively idle: only {issues_open_now} open issues and "
            f"{wip_count} open PRs remain. The backlog has been cleared and the "
            f"pipeline is waiting for new work rather than being constrained."
        )

    return {
        "repo": repo_name,
        "adoption_date": adoption.strftime("%Y-%m-%d"),
        "days_since_adoption": days_since_adoption,
        "weeks_since_adoption": round(weeks_since_adoption, 1),

        # Pipeline inventory — PR path
        "ra_prs_total": len(ra_prs),
        "ra_prs_merged": len(ra_merged),
        "ra_prs_open": len(ra_open),
        "ra_prs_closed_unmerged": len(ra_closed_unmerged),

        # Pipeline inventory — Comment path
        "comment_path_total": len(comment_path_issues),
        "comment_path_closed": len(comment_path_closed),
        "comment_path_open": len(comment_path_open),
        "pr_path_issues": len(pr_path_issues),

        # Combined throughput (both paths)
        "total_issues_acted_on": len(comment_path_issues) + len(pr_path_issues),
        "total_issues_resolved": len(comment_path_closed) + sum(1 for n in pr_path_issues if n in issue_map and issue_map[n]["state"] == "closed"),

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

    colors = [STATUS_COLORS.get(r["bottleneck_status"], COLORS["muted"]) for r in results]

    # === Graph 1: Pipeline Flow Diagram (stacked bar — dual path) ===
    merged = [r["ra_prs_merged"] for r in results]
    still_open = [r["ra_prs_open"] for r in results]
    closed_unmerged = [r["ra_prs_closed_unmerged"] for r in results]
    cmt_closed = [r["comment_path_closed"] for r in results]
    cmt_open = [r["comment_path_open"] for r in results]

    fig = make_figure(
        title="Dual-Path Pipeline Flow: Comment Path + PR Path<br>"
              "<sup>(labels show resolved/total issues acted on)</sup>",
        width=1200, height=700,
    )
    fig.add_trace(go.Bar(name="Comment path → closed (no PR needed)", x=repos, y=cmt_closed, marker_color=COLORS["secondary"]))
    fig.add_trace(go.Bar(name="Comment path → still open", x=repos, y=cmt_open, marker_color=COLORS["muted"]))
    fig.add_trace(go.Bar(name="PR path → merged", x=repos, y=merged, marker_color=COLORS["primary"]))
    fig.add_trace(go.Bar(name="PR path → awaiting review (WIP)", x=repos, y=still_open, marker_color=COLORS["accent"]))
    fig.add_trace(go.Bar(name="PR path → rejected", x=repos, y=closed_unmerged, marker_color=COLORS["sand"]))
    fig.update_layout(
        barmode="stack",
        xaxis_title="Repository",
        yaxis_title="Issues Acted On by Repo-Assist",
        legend=dict(font=dict(size=10), yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    # Add total count annotations
    cmt_top = [cc + co for cc, co in zip(cmt_closed, cmt_open)]
    for i, r in enumerate(results):
        total = cmt_top[i] + r["ra_prs_total"]
        fig.add_annotation(
            x=repos[i], y=total,
            text=f"<b>{merged[i]+cmt_closed[i]}/{total}</b>",
            showarrow=False, yshift=12,
            font=dict(size=11, color=colors[i]),
        )
    save_figure(fig, os.path.join(output_dir, "bottleneck-pipeline-flow.png"))

    # === Graph 2: Throughput ratio with bottleneck status ===
    fig = make_figure(
        title="Pipeline Throughput Ratio: PR Merge Rate / PR Creation Rate<br>"
              "<sup>(Dark Red = BLOCKED, Teal = FLOWING, Light Teal = IDLE)</sup>",
        width=1200, height=600,
    )
    fig.add_trace(go.Bar(
        x=repos,
        y=[r["throughput_ratio"] * 100 for r in results],
        marker_color=colors,
        showlegend=False,
    ))
    fig.add_hline(y=75, line_dash="dash", line_color=COLORS["secondary"], line_width=1,
                  annotation_text="Healthy (75%)", annotation_position="top left",
                  annotation_font=dict(color=COLORS["secondary"], size=11))
    fig.add_hline(y=50, line_dash="dash", line_color=COLORS["accent"], line_width=1,
                  annotation_text="Warning (50%)", annotation_position="bottom left",
                  annotation_font=dict(color=COLORS["accent"], size=11))
    fig.update_layout(
        xaxis_title="Repository",
        yaxis_title="Throughput Ratio (%)",
        yaxis=dict(range=[0, 105], ticksuffix="%"),
    )
    save_figure(fig, os.path.join(output_dir, "bottleneck-throughput-ratio.png"))

    # === Graph 3: Cycle Time Comparison (merged vs waiting) ===
    merge_times = [r["merge_cycle_time_avg"] or 0 for r in results]
    wait_times = [r["open_wait_time_avg"] or 0 for r in results]

    fig = make_figure(
        title="Cycle Time: Merged PRs vs Still-Waiting PRs<br>"
              "<sup>(Amber >> Teal indicates review bottleneck)</sup>",
        width=1200, height=600,
    )
    fig.add_trace(go.Bar(
        name="Avg merge cycle time (completed)",
        x=repos, y=merge_times,
        marker_color=COLORS["secondary"],
    ))
    fig.add_trace(go.Bar(
        name="Avg wait time (still open)",
        x=repos, y=wait_times,
        marker_color=COLORS["accent"],
    ))
    fig.update_layout(
        barmode="group",
        xaxis_title="Repository",
        yaxis_title="Days",
    )
    save_figure(fig, os.path.join(output_dir, "bottleneck-cycle-times.png"))

    # === Graph 4: WIP Accumulation ===
    fig = make_figure(
        title="Work-In-Progress: Repo-Assist PRs Awaiting Human Review",
        width=1200, height=600,
    )
    fig.add_trace(go.Bar(
        x=repos,
        y=[r["wip_count"] for r in results],
        marker_color=colors,
        showlegend=False,
    ))
    for i, r in enumerate(results):
        if r["wip_count"] > 0:
            fig.add_annotation(
                x=repos[i], y=r["wip_count"],
                text=f"<b>{r['bottleneck_status']}</b>",
                showarrow=False, yshift=14,
                font=dict(size=10, color=colors[i]),
            )
    fig.update_layout(
        xaxis_title="Repository",
        yaxis_title="Open Repo-Assist PRs (WIP)",
    )
    save_figure(fig, os.path.join(output_dir, "bottleneck-wip.png"))

    # === Graph 5: Bottleneck Impact — combined resolution rate vs backlog clearance ===
    resolution_rates = []
    for r in results:
        total_acted = r["comment_path_total"] + r["ra_prs_total"]
        total_resolved = r["comment_path_closed"] + r["ra_prs_merged"]
        resolution_rates.append(total_resolved / total_acted * 100 if total_acted > 0 else 0)

    clearances = []
    for r in results:
        oaa = r["issues_open_at_adoption"]
        closed = r["issues_closed_after_adoption"]
        clearances.append(min(closed / oaa * 100, 100) if oaa > 0 else 0)

    labels = [r["repo"].split("/")[1] if "/" in r["repo"] else r["repo"] for r in results]

    fig = make_figure(
        title="Pipeline Impact: Combined Resolution Rate vs Backlog Clearance<br>"
              "<sup>(includes both comment-path closures and PR merges)</sup>",
        width=1000, height=800,
    )
    fig.add_trace(go.Scatter(
        x=resolution_rates, y=clearances,
        mode="markers+text",
        text=labels,
        textposition="top right",
        textfont=dict(size=11),
        marker=dict(size=16, color=colors, line=dict(width=1, color=COLORS["dark"])),
        showlegend=False,
    ))
    fig.add_vline(x=50, line_dash="dash", line_color=COLORS["accent"], opacity=0.4)
    fig.add_vline(x=75, line_dash="dash", line_color=COLORS["secondary"], opacity=0.4)
    fig.update_layout(
        xaxis_title="Combined Resolution Rate (% of issues acted on → resolved)",
        yaxis_title="Backlog Clearance (%)",
        xaxis=dict(range=[-5, 105]),
        yaxis=dict(range=[-5, 105]),
    )
    save_figure(fig, os.path.join(output_dir, "bottleneck-impact-scatter.png"))


def print_summary(all_results):
    """Print a text summary of the bottleneck analysis."""
    results = [r for r in all_results if r is not None]
    results.sort(key=lambda r: r["throughput_ratio"])

    print("\n" + "=" * 100)
    print("PIPELINE BOTTLENECK ANALYSIS — REPO-ASSIST REPOSITORIES")
    print("=" * 100)
    print()
    print(f"\n{'Repository':<35} {'Status':<12} {'Type':<10} {'RA PRs':>7} {'Merged':>7} {'Reject':>7} {'Open':>5} "
          f"{'Thru%':>6} {'Rej%':>5} {'WIP%':>5} {'CmtPath':>8} {'CmtCls':>7} "
          f"{'MergeCT':>8} {'WaitCT':>8}")
    print("-" * 140)

    for r in results:
        repo = r["repo"]
        print(f"{repo:<35} {r['bottleneck_status']:<12} {r['bottleneck_type']:<10} "
              f"{r['ra_prs_total']:>7} "
              f"{r['ra_prs_merged']:>7} {r['ra_prs_closed_unmerged']:>7} {r['ra_prs_open']:>5} "
              f"{r['throughput_ratio']*100:>5.0f}% {r['rejection_rate']*100:>4.0f}% "
              f"{r['wip_fraction']*100:>4.0f}% "
              f"{r['comment_path_total']:>8} {r['comment_path_closed']:>7} "
              f"{r['merge_cycle_time_avg'] or 0:>7.1f}d "
              f"{r['open_wait_time_avg'] or 0:>7.1f}d")

    print()
    print("BOTTLENECK DETAILS:")
    print("-" * 140)
    for r in results:
        if r["bottleneck_status"] != "FLOWING":
            print(f"\n  {r['repo']} [{r['bottleneck_status']}] — type: {r['bottleneck_type']}:")
            print(f"    Summary: {r['bottleneck_detail']}")
            if r["comment_path_total"] > 0:
                print(f"    Comment path: {r['comment_path_total']} issues investigated, "
                      f"{r['comment_path_closed']} closed (no PR needed), "
                      f"{r['comment_path_open']} still open")
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
