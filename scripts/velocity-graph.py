#!/usr/bin/env python3
"""
Generate a velocity comparison graph showing before/after repo-assist adoption.
Uses a dot-and-arrow style to emphasize the magnitude of change.
"""

import json
import os
import sys

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from chart_theme import make_figure, save_figure, COLORS, PALETTE, BEFORE_COLOR, AFTER_COLOR, AFTER_COLOR_ALT, get_theme


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "graphs"

    analysis = json.load(open(os.path.join(
        os.path.dirname(data_dir) if data_dir != "data" else ".", "analysis.json")))

    # Extract before/after data
    repos = []
    for m in analysis:
        ba = m.get("before_after")
        if ba:
            repos.append({
                "name": m["repo"].split("/")[1] if "/" in m["repo"] else m["repo"],
                "full": m["repo"],
                "before_issues": ba["before_issues_closed_per_week"],
                "after_issues": ba["after_issues_closed_per_week"],
                "before_prs": ba["before_prs_merged_per_week"],
                "after_prs": ba["after_prs_merged_per_week"],
            })

    # Sort by issue velocity increase
    repos.sort(key=lambda r: r["after_issues"] - r["before_issues"], reverse=True)

    n = len(repos)
    names = [r["name"] for r in repos]

    before_i = [r["before_issues"] for r in repos]
    after_i = [r["after_issues"] for r in repos]
    before_p = [r["before_prs"] for r in repos]
    after_p = [r["after_prs"] for r in repos]

    fig = make_subplots(
        rows=1, cols=2,
        shared_yaxes=True,
        subplot_titles=("Issue Closure Velocity", "PR Merge Velocity"),
        horizontal_spacing=0.08,
    )

    # --- Left subplot: Issue Closure Velocity ---
    for i in range(n):
        fig.add_trace(go.Scatter(
            x=[before_i[i], after_i[i]], y=[names[i], names[i]],
            mode="lines", line=dict(color=COLORS["muted"], width=2),
            showlegend=False,
        ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=before_i, y=names, mode="markers",
        marker=dict(color=BEFORE_COLOR, size=12),
        name="Before adoption",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=after_i, y=names, mode="markers",
        marker=dict(color=AFTER_COLOR, size=12),
        name="After adoption",
    ), row=1, col=1)

    for i in range(n):
        mult = f"{after_i[i] / before_i[i]:.0f}×" if before_i[i] > 0 else "∞"
        fig.add_annotation(
            x=after_i[i], y=names[i], text=mult,
            xanchor="left", xshift=8,
            font=dict(size=11, color=AFTER_COLOR),
            showarrow=False, row=1, col=1,
        )

    # --- Right subplot: PR Merge Velocity ---
    for i in range(n):
        fig.add_trace(go.Scatter(
            x=[before_p[i], after_p[i]], y=[names[i], names[i]],
            mode="lines", line=dict(color=COLORS["muted"], width=2),
            showlegend=False,
        ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=before_p, y=names, mode="markers",
        marker=dict(color=BEFORE_COLOR, size=12),
        name="Before adoption", showlegend=False,
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=after_p, y=names, mode="markers",
        marker=dict(color=AFTER_COLOR_ALT, size=12),
        name="After adoption (PRs)", showlegend=False,
    ), row=1, col=2)

    for i in range(n):
        mult = f"{after_p[i] / before_p[i]:.0f}×" if before_p[i] > 0 else "∞"
        fig.add_annotation(
            x=after_p[i], y=names[i], text=mult,
            xanchor="left", xshift=8,
            font=dict(size=11, color=AFTER_COLOR_ALT),
            showarrow=False, row=1, col=2,
        )

    # Layout
    theme = get_theme()
    fig.update_layout(
        title_text="Velocity Before and After Repo-Assist Adoption",
        title_font=dict(size=16),
        title_x=0.5,
        width=1200, height=max(500, n * 50 + 200),
        paper_bgcolor=theme.get("paper_bgcolor", "#FFFFFF"),
        plot_bgcolor=theme.get("plot_bgcolor", "#FAFAFA"),
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.15,
            xanchor="center", x=0.5,
        ),
    )
    fig.update_xaxes(title_text="Issues Closed per Week", row=1, col=1,
                     gridcolor=theme.get("xaxis", {}).get("gridcolor", "#E0E0E0"))
    fig.update_xaxes(title_text="PRs Merged per Week", row=1, col=2,
                     gridcolor=theme.get("xaxis", {}).get("gridcolor", "#E0E0E0"))
    fig.update_yaxes(autorange="reversed", row=1, col=1)

    output_path = os.path.join(output_dir, "velocity-before-after.png")
    save_figure(fig, output_path)


if __name__ == "__main__":
    main()
