#!/usr/bin/env python3
"""
Analyze the impact of the repo-assist workflow on repository velocity and quality.

Usage: python3 analyze-repo-assist.py DATA_DIR [--months N] [--output OUTPUT_DIR]

Detects repo-assist activity by looking for:
  - PRs with "[repo-assist]" in title
  - Issues/PRs with "repo-assist" label
  - Comments mentioning "Repo Assist"

Computes metrics:
  - Velocity: issues closed per week, PRs merged per week
  - Quality: proportion of 6-month-ago backlog that has been addressed
  - Before/after comparison around repo-assist adoption date

Outputs:
  - analysis.json: raw computed metrics
  - comparative graphs (PNG)
  - report.md: narrative report
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
from chart_theme import make_figure, save_figure, COLORS, PALETTE, color_with_alpha


def parse_dt(s):
    if s is None:
        return None
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def detect_repo_assist(data_dir):
    """Detect repo-assist activity and estimate adoption date."""
    pulls_path = os.path.join(data_dir, "pulls.json")
    issues_path = os.path.join(data_dir, "issues-raw.json")

    pulls = load_json(pulls_path) if os.path.exists(pulls_path) else []
    all_issues = load_json(issues_path) if os.path.exists(issues_path) else []

    ra_prs = []
    for pr in pulls:
        title = pr.get("title", "")
        labels = [l.get("name", "") for l in pr.get("labels", [])]
        if "[repo-assist]" in title.lower() or "[Repo Assist]" in title or "repo-assist" in labels:
            ra_prs.append(pr)

    ra_issues = []
    for issue in all_issues:
        labels = [l.get("name", "") for l in issue.get("labels", [])]
        title = issue.get("title", "")
        if "repo-assist" in labels or "[repo-assist]" in title.lower() or "[Repo Assist]" in title:
            ra_issues.append(issue)

    # Earliest repo-assist PR or issue creation date = adoption date
    ra_dates = []
    for item in ra_prs + ra_issues:
        dt = parse_dt(item.get("created_at"))
        if dt:
            ra_dates.append(dt)

    adoption_date = min(ra_dates) if ra_dates else None

    return {
        "ra_pr_count": len(ra_prs),
        "ra_issue_count": len(ra_issues),
        "adoption_date": adoption_date,
        "ra_prs": ra_prs,
    }


def compute_metrics(data_dir, months=6):
    """Compute velocity and quality metrics for a repo."""
    issues = load_json(os.path.join(data_dir, "issues.json"))
    pulls = load_json(os.path.join(data_dir, "pulls.json"))
    meta = load_json(os.path.join(data_dir, "metadata.json"))

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=months * 30)
    six_months_ago = cutoff

    ra_info = detect_repo_assist(data_dir)

    # --- Backlog 6 months ago ---
    open_at_cutoff = 0
    for issue in issues:
        created = parse_dt(issue["created_at"])
        closed = parse_dt(issue.get("closed_at"))
        if created and created <= six_months_ago:
            if closed is None or closed > six_months_ago:
                open_at_cutoff += 1

    # --- Current open ---
    open_now = sum(1 for i in issues if i.get("state") == "open")

    # --- Backlog addressed: issues that were open 6mo ago and are now closed ---
    backlog_addressed = 0
    for issue in issues:
        created = parse_dt(issue["created_at"])
        closed = parse_dt(issue.get("closed_at"))
        if created and created <= six_months_ago:
            if closed and closed > six_months_ago:
                backlog_addressed += 1

    backlog_ratio = backlog_addressed / open_at_cutoff if open_at_cutoff > 0 else 0

    # --- New issues in period ---
    new_issues = sum(1 for i in issues if parse_dt(i["created_at"]) and parse_dt(i["created_at"]) >= six_months_ago)

    # --- Issues closed in period ---
    issues_closed = sum(1 for i in issues
                        if parse_dt(i.get("closed_at")) and parse_dt(i.get("closed_at")) >= six_months_ago)

    # --- PRs merged in period ---
    prs_merged = sum(1 for p in pulls
                     if parse_dt(p.get("merged_at")) and parse_dt(p.get("merged_at")) >= six_months_ago)

    # --- Weekly rates ---
    weeks = months * 4.33
    issues_closed_per_week = issues_closed / weeks if weeks > 0 else 0
    prs_merged_per_week = prs_merged / weeks if weeks > 0 else 0
    new_issues_per_week = new_issues / weeks if weeks > 0 else 0

    # --- Before/after adoption comparison ---
    before_after = None
    if ra_info["adoption_date"]:
        adoption = ra_info["adoption_date"]
        # "Before" period: same length before adoption as after
        after_days = (now - adoption).days
        before_start = adoption - timedelta(days=after_days)

        before_closed = 0
        after_closed = 0
        before_merged = 0
        after_merged = 0

        for issue in issues:
            closed = parse_dt(issue.get("closed_at"))
            if closed:
                if before_start <= closed < adoption:
                    before_closed += 1
                elif adoption <= closed <= now:
                    after_closed += 1

        for pr in pulls:
            merged = parse_dt(pr.get("merged_at"))
            if merged:
                if before_start <= merged < adoption:
                    before_merged += 1
                elif adoption <= merged <= now:
                    after_merged += 1

        before_weeks = max(after_days / 7, 1)
        after_weeks = max(after_days / 7, 1)

        # Backlog at adoption date
        open_at_adoption = 0
        for issue in issues:
            created = parse_dt(issue["created_at"])
            closed = parse_dt(issue.get("closed_at"))
            if created and created <= adoption:
                if closed is None or closed > adoption:
                    open_at_adoption += 1

        # How many of those were addressed since adoption
        adoption_backlog_addressed = 0
        for issue in issues:
            created = parse_dt(issue["created_at"])
            closed = parse_dt(issue.get("closed_at"))
            if created and created <= adoption:
                if closed and closed > adoption:
                    adoption_backlog_addressed += 1

        before_after = {
            "adoption_date": adoption.strftime("%Y-%m-%d"),
            "period_days": after_days,
            "before_issues_closed": before_closed,
            "after_issues_closed": after_closed,
            "before_issues_closed_per_week": before_closed / before_weeks,
            "after_issues_closed_per_week": after_closed / after_weeks,
            "before_prs_merged": before_merged,
            "after_prs_merged": after_merged,
            "before_prs_merged_per_week": before_merged / before_weeks,
            "after_prs_merged_per_week": after_merged / after_weeks,
            "open_at_adoption": open_at_adoption,
            "adoption_backlog_addressed": adoption_backlog_addressed,
            "adoption_backlog_ratio": adoption_backlog_addressed / open_at_adoption if open_at_adoption > 0 else 0,
        }

    # Repo-assist specific PRs merged
    ra_prs_merged = sum(1 for p in ra_info["ra_prs"]
                        if parse_dt(p.get("merged_at")) is not None)

    return {
        "repo": meta.get("repo", "unknown"),
        "has_repo_assist": ra_info["adoption_date"] is not None,
        "adoption_date": ra_info["adoption_date"].strftime("%Y-%m-%d") if ra_info["adoption_date"] else None,
        "ra_prs_total": ra_info["ra_pr_count"],
        "ra_prs_merged": ra_prs_merged,
        "open_6mo_ago": open_at_cutoff,
        "open_now": open_now,
        "net_change": open_now - open_at_cutoff,
        "backlog_addressed": backlog_addressed,
        "backlog_ratio": round(backlog_ratio, 3),
        "new_issues_in_period": new_issues,
        "issues_closed_in_period": issues_closed,
        "prs_merged_in_period": prs_merged,
        "issues_closed_per_week": round(issues_closed_per_week, 2),
        "prs_merged_per_week": round(prs_merged_per_week, 2),
        "new_issues_per_week": round(new_issues_per_week, 2),
        "before_after": before_after,
    }


def generate_comparative_graphs(all_metrics, output_dir):
    """Generate comparative bar charts across all repos."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    repos = [m["repo"].split("/")[1] if "/" in m["repo"] else m["repo"] for m in all_metrics]
    has_ra = [m["has_repo_assist"] for m in all_metrics]
    colors = [COLORS["primary"] if ra else COLORS["muted"] for ra in has_ra]

    subtitle = "<br><sub>(Dark Cyan = has repo-assist, Light Teal = no repo-assist)</sub>"

    # 1. Open issues: 6 months ago vs now
    fig = make_figure("Open Issues: 6 Months Ago vs Now" + subtitle)
    fig.add_trace(go.Bar(
        x=repos, y=[m["open_6mo_ago"] for m in all_metrics],
        name="6 months ago", marker_color=COLORS["sand"],
    ))
    fig.add_trace(go.Bar(
        x=repos, y=[m["open_now"] for m in all_metrics],
        name="Now", marker_color=colors,
    ))
    fig.update_layout(barmode="group", xaxis_title="Repository", yaxis_title="Open Issues")
    save_figure(fig, os.path.join(output_dir, "comparative-open-issues.png"))

    # 2. Backlog addressed ratio
    backlog_pct = [m["backlog_ratio"] * 100 for m in all_metrics]
    text_labels = [f'{m["backlog_addressed"]}/{m["open_6mo_ago"]}' for m in all_metrics]
    fig = make_figure("Backlog Addressed (Quality Metric)" + subtitle)
    fig.add_trace(go.Bar(
        x=repos, y=backlog_pct, marker_color=colors,
        text=text_labels, textposition="outside", textfont=dict(size=10),
    ))
    fig.update_layout(
        yaxis_title="% of 6-month-ago backlog addressed",
        yaxis_ticksuffix="%",
    )
    save_figure(fig, os.path.join(output_dir, "comparative-backlog-addressed.png"))

    # 3. Issues closed per week (velocity)
    fig = make_figure("Issue Closure Velocity" + subtitle)
    fig.add_trace(go.Bar(
        x=repos, y=[m["issues_closed_per_week"] for m in all_metrics],
        marker_color=colors,
    ))
    fig.update_layout(yaxis_title="Issues Closed per Week")
    save_figure(fig, os.path.join(output_dir, "comparative-issue-velocity.png"))

    # 4. PRs merged per week
    fig = make_figure("PR Merge Velocity" + subtitle)
    fig.add_trace(go.Bar(
        x=repos, y=[m["prs_merged_per_week"] for m in all_metrics],
        marker_color=colors,
    ))
    fig.update_layout(yaxis_title="PRs Merged per Week")
    save_figure(fig, os.path.join(output_dir, "comparative-pr-velocity.png"))

    # 5. Before/after adoption (for repos that have it)
    ra_metrics = [m for m in all_metrics if m["before_after"]]
    if ra_metrics:
        ra_repos = [m["repo"].split("/")[1] for m in ra_metrics]

        fig = make_subplots(rows=1, cols=2, subplot_titles=[
            "Issue Closure: Before vs After",
            "PR Merge Rate: Before vs After",
        ])

        before_issue = [m["before_after"]["before_issues_closed_per_week"] for m in ra_metrics]
        after_issue = [m["before_after"]["after_issues_closed_per_week"] for m in ra_metrics]
        fig.add_trace(go.Bar(x=ra_repos, y=before_issue, name="Before repo-assist",
                             marker_color=COLORS["sand"]), row=1, col=1)
        fig.add_trace(go.Bar(x=ra_repos, y=after_issue, name="After repo-assist",
                             marker_color=COLORS["primary"]), row=1, col=1)

        before_pr = [m["before_after"]["before_prs_merged_per_week"] for m in ra_metrics]
        after_pr = [m["before_after"]["after_prs_merged_per_week"] for m in ra_metrics]
        fig.add_trace(go.Bar(x=ra_repos, y=before_pr, name="Before repo-assist",
                             marker_color=COLORS["sand"], showlegend=False), row=1, col=2)
        fig.add_trace(go.Bar(x=ra_repos, y=after_pr, name="After repo-assist",
                             marker_color=COLORS["primary"], showlegend=False), row=1, col=2)

        from chart_theme import get_theme
        fig.update_layout(**get_theme(), barmode="group", width=1200, height=600,
                          yaxis_title="Issues Closed / Week", yaxis2_title="PRs Merged / Week")
        save_figure(fig, os.path.join(output_dir, "comparative-before-after.png"))

    # 6. Net change in open issues
    net = [m["net_change"] for m in all_metrics]
    bar_colors = [COLORS["secondary"] if n < 0 else COLORS["danger"] for n in net]
    annotations = ["RA" if has_ra[i] else "" for i in range(len(repos))]
    fig = make_figure(
        "Net Change in Open Issues (Last 6 Months)"
        "<br><sub>(Teal = reduced backlog, Dark Red = growing backlog)</sub>"
    )
    fig.add_trace(go.Bar(
        x=repos, y=net, marker_color=bar_colors,
        text=annotations, textposition="outside",
        textfont=dict(size=10, color=COLORS["primary"]),
    ))
    fig.update_layout(yaxis_title="Net Change in Open Issues")
    fig.add_hline(y=0, line_width=1, line_color=COLORS["dark"])
    save_figure(fig, os.path.join(output_dir, "comparative-net-change.png"))


def generate_report(all_metrics, output_dir):
    """Generate a markdown report."""
    ra_repos = [m for m in all_metrics if m["has_repo_assist"]]
    non_ra_repos = [m for m in all_metrics if not m["has_repo_assist"]]

    def avg(lst, key):
        vals = [m[key] for m in lst]
        return sum(vals) / len(vals) if vals else 0

    report = []
    report.append("# Repo-Assist Impact Analysis")
    report.append("")
    report.append(f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    report.append(f"**Period**: Last 6 months")
    report.append(f"**Repositories analyzed**: {len(all_metrics)}")
    report.append(f"**With repo-assist**: {len(ra_repos)}")
    report.append(f"**Without repo-assist**: {len(non_ra_repos)}")
    report.append("")

    # Executive summary
    report.append("## Executive Summary")
    report.append("")

    if ra_repos and non_ra_repos:
        ra_velocity = avg(ra_repos, "issues_closed_per_week")
        non_ra_velocity = avg(non_ra_repos, "issues_closed_per_week")
        ra_quality = avg(ra_repos, "backlog_ratio") * 100
        non_ra_quality = avg(non_ra_repos, "backlog_ratio") * 100
        ra_pr_velocity = avg(ra_repos, "prs_merged_per_week")
        non_ra_pr_velocity = avg(non_ra_repos, "prs_merged_per_week")

        report.append(f"Repositories using repo-assist show an average issue closure rate of "
                      f"**{ra_velocity:.1f} issues/week** compared to **{non_ra_velocity:.1f} issues/week** "
                      f"for repositories without it.")
        report.append("")
        report.append(f"PR merge velocity averages **{ra_pr_velocity:.1f} PRs/week** with repo-assist "
                      f"vs **{non_ra_pr_velocity:.1f} PRs/week** without.")
        report.append("")
        report.append(f"Backlog quality (proportion of 6-month-ago open issues now addressed): "
                      f"**{ra_quality:.1f}%** with repo-assist vs **{non_ra_quality:.1f}%** without.")
        report.append("")

        # Net backlog change
        ra_net = avg(ra_repos, "net_change")
        non_ra_net = avg(non_ra_repos, "net_change")
        report.append(f"Average net change in open issues: **{ra_net:+.1f}** (repo-assist) "
                      f"vs **{non_ra_net:+.1f}** (no repo-assist).")
    report.append("")

    # Detailed table
    report.append("## Repository Comparison")
    report.append("")
    report.append("| Repository | Repo-Assist | Adoption Date | Open 6mo ago | Open Now | Net Change | Backlog Addressed | Issues Closed/wk | PRs Merged/wk |")
    report.append("|---|---|---|---|---|---|---|---|---|")
    for m in sorted(all_metrics, key=lambda x: x["repo"]):
        repo = m["repo"]
        ra = "Yes" if m["has_repo_assist"] else "No"
        adoption = m["adoption_date"] or "—"
        report.append(f"| {repo} | {ra} | {adoption} | {m['open_6mo_ago']} | {m['open_now']} | {m['net_change']:+d} | "
                      f"{m['backlog_addressed']}/{m['open_6mo_ago']} ({m['backlog_ratio']*100:.1f}%) | "
                      f"{m['issues_closed_per_week']} | {m['prs_merged_per_week']} |")
    report.append("")

    # Before/after section
    ba_repos = [m for m in all_metrics if m["before_after"]]
    if ba_repos:
        report.append("## Before/After Repo-Assist Adoption")
        report.append("")
        report.append("For repositories with repo-assist, comparing equal-length periods before and after adoption:")
        report.append("")
        report.append("| Repository | Adoption | Period (days) | Issues Closed/wk Before | After | Change | PRs Merged/wk Before | After | Change | Backlog at Adoption | Addressed Since |")
        report.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for m in ba_repos:
            ba = m["before_after"]
            ic_before = ba["before_issues_closed_per_week"]
            ic_after = ba["after_issues_closed_per_week"]
            ic_change = ic_after - ic_before
            pm_before = ba["before_prs_merged_per_week"]
            pm_after = ba["after_prs_merged_per_week"]
            pm_change = pm_after - pm_before
            report.append(f"| {m['repo']} | {ba['adoption_date']} | {ba['period_days']} | "
                          f"{ic_before:.2f} | {ic_after:.2f} | {ic_change:+.2f} | "
                          f"{pm_before:.2f} | {pm_after:.2f} | {pm_change:+.2f} | "
                          f"{ba['open_at_adoption']} | {ba['adoption_backlog_addressed']} ({ba['adoption_backlog_ratio']*100:.1f}%) |")
        report.append("")

    # Repo-assist contribution details
    if ra_repos:
        report.append("## Repo-Assist Contribution Details")
        report.append("")
        report.append("| Repository | RA PRs Created | RA PRs Merged |")
        report.append("|---|---|---|")
        for m in ra_repos:
            report.append(f"| {m['repo']} | {m['ra_prs_total']} | {m['ra_prs_merged']} |")
        report.append("")

    # Per-repo sections with graphs
    report.append("## Per-Repository Graphs")
    report.append("")
    for m in sorted(all_metrics, key=lambda x: x["repo"]):
        safe = m["repo"].replace("/", "-")
        report.append(f"### {m['repo']}")
        if m["has_repo_assist"]:
            report.append(f"*Repo-assist active since {m['adoption_date']}*")
        else:
            report.append("*No repo-assist*")
        report.append("")
        report.append(f"| Metric | Value |")
        report.append(f"|---|---|")
        report.append(f"| Open issues (6mo ago → now) | {m['open_6mo_ago']} → {m['open_now']} ({m['net_change']:+d}) |")
        report.append(f"| Backlog addressed | {m['backlog_addressed']}/{m['open_6mo_ago']} ({m['backlog_ratio']*100:.1f}%) |")
        report.append(f"| Issues closed/week | {m['issues_closed_per_week']} |")
        report.append(f"| PRs merged/week | {m['prs_merged_per_week']} |")
        report.append(f"| New issues/week | {m['new_issues_per_week']} |")
        report.append("")
        report.append(f"![Open Issues](graphs/{safe}/open-issues-over-time.png)")
        report.append(f"![Merge Rate](graphs/{safe}/merge-rate.png)")
        report.append(f"![PR Time to Merge](graphs/{safe}/pr-time-to-merge.png)")
        report.append(f"![Issue Activity](graphs/{safe}/issue-activity.png)")
        report.append("")

    # Comparative graphs
    report.append("## Comparative Graphs")
    report.append("")
    report.append("![Open Issues Comparison](graphs/comparative-open-issues.png)")
    report.append("![Backlog Addressed](graphs/comparative-backlog-addressed.png)")
    report.append("![Issue Velocity](graphs/comparative-issue-velocity.png)")
    report.append("![PR Velocity](graphs/comparative-pr-velocity.png)")
    report.append("![Net Change](graphs/comparative-net-change.png)")
    if ba_repos:
        report.append("![Before/After](graphs/comparative-before-after.png)")
    report.append("")

    # Methodology
    report.append("## Methodology")
    report.append("")
    report.append("- **Velocity** is measured as issues closed per week and PRs merged per week over the 6-month analysis period.")
    report.append("- **Quality** is measured as the proportion of the known backlog (open issues 6 months ago) that has been addressed (closed) during the period.")
    report.append("- **Repo-assist detection**: A repository is classified as using repo-assist if it has PRs with `[repo-assist]` in the title or issues/PRs with the `repo-assist` label. The adoption date is the earliest such item.")
    report.append("- **Before/after comparison**: For repos with repo-assist, we compare an equal-length period before adoption to the period after adoption.")
    report.append("- **Limitations**: Correlation does not imply causation. Repos using repo-assist may differ from non-users in maintainer activity, community size, project maturity, and other factors. The before/after comparison within the same repo is more informative than cross-repo comparisons.")
    report.append("")

    report_text = "\n".join(report)
    report_path = os.path.join(output_dir, "graphs", "report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report_text)
    print(f"Report saved to {report_path}")
    return report_text


def main():
    parser = argparse.ArgumentParser(description="Analyze repo-assist impact.")
    parser.add_argument("data_dir", nargs="?", default="./data", help="Directory containing per-repo data subdirectories")
    parser.add_argument("--months", "-m", type=int, default=6)
    parser.add_argument("--output", "-o", default=None, help="Output directory (default: parent of data_dir)")
    args = parser.parse_args()

    data_dir = args.data_dir
    output_dir = args.output or os.path.dirname(os.path.abspath(data_dir))

    # Find all repo data dirs
    repo_dirs = sorted([
        os.path.join(data_dir, d)
        for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d)) and os.path.exists(os.path.join(data_dir, d, "metadata.json"))
    ])

    print(f"Found {len(repo_dirs)} repositories")

    all_metrics = []
    for repo_dir in repo_dirs:
        print(f"  Analyzing {os.path.basename(repo_dir)}...")
        metrics = compute_metrics(repo_dir, args.months)
        all_metrics.append(metrics)

    # Save raw analysis
    analysis_path = os.path.join(output_dir, "analysis.json")
    with open(analysis_path, "w") as f:
        json.dump(all_metrics, f, indent=2)
    print(f"Analysis saved to {analysis_path}")

    # Generate comparative graphs
    graphs_dir = os.path.join(output_dir, "graphs")
    os.makedirs(graphs_dir, exist_ok=True)
    print("Generating comparative graphs...")
    generate_comparative_graphs(all_metrics, graphs_dir)

    # Generate report
    print("Generating report...")
    generate_report(all_metrics, output_dir)


if __name__ == "__main__":
    main()
