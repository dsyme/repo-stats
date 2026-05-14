#!/usr/bin/env python3
"""Strip unused fields from data JSON files to reduce repository size.

Keeps only fields actually used by the analysis scripts:
  pulls.json:        number, title, state, labels, created_at, merged_at, closed_at, draft, html_url
  issues-raw.json:   number, title, labels, created_at, pull_request
  issues.json:       number, title, labels, state, created_at, closed_at, author_association, user.login
  issue-events.json: id, event, created_at, actor.login, issue.number
  labels[]:          name (only)
"""
import json, os, sys, glob

PULLS_KEEP = ["number", "title", "state", "labels", "created_at", "merged_at", "closed_at", "draft", "html_url"]
ISSUES_RAW_KEEP = ["number", "title", "labels", "created_at", "pull_request"]
ISSUES_KEEP = ["number", "title", "labels", "state", "created_at", "closed_at", "author_association"]

def slim_labels(labels):
    """Keep only the 'name' field from each label."""
    if not labels:
        return labels
    return [{"name": l.get("name", "")} for l in labels if isinstance(l, dict)]

def slim_pull_request(pr_obj):
    """For issues-raw.json pull_request field, keep just a marker."""
    if pr_obj is None:
        return None
    # The scripts only check `select(.pull_request == null)` so we just need it to be non-null
    return {}

def slim_pulls(data):
    result = []
    for item in data:
        r = {k: item[k] for k in PULLS_KEEP if k in item}
        if "labels" in r:
            r["labels"] = slim_labels(r["labels"])
        result.append(r)
    return result

def slim_issues_raw(data):
    result = []
    for item in data:
        r = {k: item[k] for k in ISSUES_RAW_KEEP if k in item}
        if "labels" in r:
            r["labels"] = slim_labels(r["labels"])
        if "pull_request" in r:
            r["pull_request"] = slim_pull_request(r["pull_request"])
        result.append(r)
    return result

def slim_issues(data):
    result = []
    for item in data:
        r = {k: item[k] for k in ISSUES_KEEP if k in item}
        if "labels" in r:
            r["labels"] = slim_labels(r["labels"])
        if "user" in item and item["user"]:
            r["user"] = {"login": item["user"].get("login", "")}
        result.append(r)
    return result

def slim_events(data):
    result = []
    for item in data:
        r = {k: item[k] for k in ["id", "event", "created_at"] if k in item}
        if "actor" in item and item["actor"]:
            r["actor"] = {"login": item["actor"].get("login", "")}
        if "issue" in item and item["issue"]:
            r["issue"] = {"number": item["issue"].get("number")}
        result.append(r)
    return result

SLIMMERS = {
    "pulls.json": slim_pulls,
    "issues-raw.json": slim_issues_raw,
    "issues.json": slim_issues,
    "issue-events.json": slim_events,
}

def process_repo(repo_dir):
    repo = os.path.basename(repo_dir)
    for fname, slimmer in SLIMMERS.items():
        path = os.path.join(repo_dir, fname)
        if not os.path.exists(path):
            continue
        old_size = os.path.getsize(path)
        with open(path) as f:
            data = json.load(f)
        slimmed = slimmer(data)
        new_json = json.dumps(slimmed, indent=2)
        new_size = len(new_json.encode("utf-8"))
        with open(path, "w") as f:
            f.write(new_json)
            f.write("\n")
        pct = (1 - new_size / old_size) * 100 if old_size > 0 else 0
        print(f"  {fname}: {old_size/1e6:.1f}MB -> {new_size/1e6:.1f}MB ({pct:.0f}% reduction)")

def main():
    data_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    repos = sorted(glob.glob(os.path.join(data_root, "*")))
    repos = [r for r in repos if os.path.isdir(r)]
    for repo_dir in repos:
        print(f"\n{os.path.basename(repo_dir)}:")
        process_repo(repo_dir)
    print("\nDone.")

if __name__ == "__main__":
    main()
