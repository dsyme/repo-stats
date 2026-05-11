#!/usr/bin/env python3
"""
Generate a velocity comparison graph showing before/after repo-assist adoption.
Uses a dot-and-arrow style to emphasize the magnitude of change.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


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
    y = np.arange(n)

    # === Graph: Horizontal dumbbell chart — before/after velocity ===
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8), sharey=True)

    names = [r["name"] for r in repos]

    # Issue closure velocity
    before_i = [r["before_issues"] for r in repos]
    after_i = [r["after_issues"] for r in repos]

    for i in range(n):
        ax1.plot([before_i[i], after_i[i]], [y[i], y[i]], color="#BDBDBD", linewidth=2, zorder=1)
        ax1.annotate("", xy=(after_i[i], y[i]), xytext=(before_i[i], y[i]),
                     arrowprops=dict(arrowstyle="->", color="#1565C0", lw=2), zorder=2)
    ax1.scatter(before_i, y, color="#FFAB91", s=80, zorder=3, label="Before adoption")
    ax1.scatter(after_i, y, color="#1565C0", s=80, zorder=3, label="After adoption")

    # Add multiplier labels
    for i in range(n):
        if before_i[i] > 0:
            mult = after_i[i] / before_i[i]
            ax1.text(after_i[i] + 0.3, y[i], f"{mult:.0f}×", va="center", fontsize=8, color="#1565C0")
        else:
            ax1.text(after_i[i] + 0.3, y[i], "∞", va="center", fontsize=8, color="#1565C0")

    ax1.set_yticks(y)
    ax1.set_yticklabels(names)
    ax1.set_xlabel("Issues Closed per Week")
    ax1.set_title("Issue Closure Velocity")
    ax1.legend(loc="lower right", fontsize=9)
    ax1.grid(True, alpha=0.3, axis="x")
    ax1.invert_yaxis()

    # PR merge velocity
    before_p = [r["before_prs"] for r in repos]
    after_p = [r["after_prs"] for r in repos]

    for i in range(n):
        ax2.plot([before_p[i], after_p[i]], [y[i], y[i]], color="#BDBDBD", linewidth=2, zorder=1)
        ax2.annotate("", xy=(after_p[i], y[i]), xytext=(before_p[i], y[i]),
                     arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=2), zorder=2)
    ax2.scatter(before_p, y, color="#FFAB91", s=80, zorder=3, label="Before adoption")
    ax2.scatter(after_p, y, color="#2E7D32", s=80, zorder=3, label="After adoption")

    for i in range(n):
        if before_p[i] > 0:
            mult = after_p[i] / before_p[i]
            ax2.text(after_p[i] + 0.3, y[i], f"{mult:.0f}×", va="center", fontsize=8, color="#2E7D32")
        else:
            ax2.text(after_p[i] + 0.3, y[i], "∞", va="center", fontsize=8, color="#2E7D32")

    ax2.set_xlabel("PRs Merged per Week")
    ax2.set_title("PR Merge Velocity")
    ax2.legend(loc="lower right", fontsize=9)
    ax2.grid(True, alpha=0.3, axis="x")

    fig.suptitle("Velocity Before and After Repo-Assist Adoption", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, "velocity-before-after.png"), dpi=150)
    plt.close(fig)
    print(f"Saved {os.path.join(output_dir, 'velocity-before-after.png')}")


if __name__ == "__main__":
    main()
