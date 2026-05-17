#!/usr/bin/env python3
"""Merge and postmerge helper for laulopezreal/getmAIlean.

Default mode is inspect-only. Mutating actions require explicit flags:

    python scripts/getmailean_merge_postmerge.py 32 --merge --postmerge --yes

State is written after each phase so another session can resume safely.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = "laulopezreal/getmAIlean"
REPO_ROOT = Path("/home/lauureal/git/getmAIlean")
WORKTREE_ROOT = Path("/home/lauureal/git/getmAIlean-worktrees")
STATE_DIR = Path("/home/lauureal/projects/getmailean/ops/merge-state")
HANDOFF_DIR = Path("/home/lauureal/common_docs_/ops/session-handoffs")
HEALTH_URL = "https://app.lauureal.xyz/health"
HOME_ENV = "/home/lauureal"
DONE_LABEL = "status:done"
ACTIVE_LABELS = ("status:claimed", "status:available")
CLOSING_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.I)


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    returncode: int


class ToolError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], *, cwd: Path = REPO_ROOT, check: bool = True) -> CommandResult:
    env = os.environ.copy()
    env["HOME"] = HOME_ENV
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise ToolError(
            "Command failed: "
            + " ".join(cmd)
            + f"\nexit={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return CommandResult(proc.stdout.strip(), proc.stderr.strip(), proc.returncode)


def gh_json(args: list[str]) -> Any:
    result = run(["gh", *args])
    if not result.stdout:
        return None
    return json.loads(result.stdout)


def pr_view(pr: int) -> dict[str, Any]:
    fields = [
        "number",
        "title",
        "state",
        "isDraft",
        "baseRefName",
        "headRefName",
        "headRefOid",
        "mergeStateStatus",
        "reviewDecision",
        "statusCheckRollup",
        "url",
        "body",
        "files",
        "mergeCommit",
        "mergedAt",
        "closed",
    ]
    return gh_json(["pr", "view", str(pr), "--repo", REPO, "--json", ",".join(fields)])


def unresolved_threads(pr: int) -> dict[str, Any]:
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          reviewDecision
          mergeStateStatus
          reviewThreads(first:100) {
            nodes {
              isResolved
              isOutdated
              path
              line
              comments(first:10) {
                nodes { author { login } bodyText url }
              }
            }
          }
        }
      }
    }
    """
    payload = gh_json(
        [
            "api",
            "graphql",
            "-f",
            "owner=laulopezreal",
            "-f",
            "repo=getmAIlean",
            "-F",
            f"number={pr}",
            "-f",
            f"query={query}",
        ]
    )
    pr_data = payload["data"]["repository"]["pullRequest"]
    unresolved = [
        node
        for node in pr_data["reviewThreads"]["nodes"]
        if not node["isResolved"] and not node["isOutdated"]
    ]
    return {
        "reviewDecision": pr_data["reviewDecision"],
        "mergeStateStatus": pr_data["mergeStateStatus"],
        "unresolved": unresolved,
        "unresolvedCount": len(unresolved),
    }


def check_summary(pr_data: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for item in pr_data.get("statusCheckRollup") or []:
        name = item.get("name") or item.get("context") or "unnamed-check"
        status = item.get("status")
        conclusion = item.get("conclusion")
        if item.get("__typename") == "StatusContext":
            state = item.get("state")
            status = "COMPLETED" if state in {"SUCCESS", "FAILURE", "ERROR"} else state
            conclusion = "SUCCESS" if state == "SUCCESS" else state
        checks.append(
            {
                "name": name,
                "status": status,
                "conclusion": conclusion,
            }
        )
    return checks


def checks_are_green(checks: list[dict[str, Any]]) -> bool:
    actionable = [
        check
        for check in checks
        if check["name"] != "unnamed-check"
        and (check.get("status") is not None or check.get("conclusion") is not None)
    ]
    return bool(actionable) and all(
        check["status"] == "COMPLETED" and check["conclusion"] in {"SUCCESS", "SKIPPED"}
        for check in actionable
    )


def readiness(pr_data: dict[str, Any], threads: dict[str, Any]) -> dict[str, Any]:
    checks = check_summary(pr_data)
    stale_review = (
        pr_data.get("reviewDecision") == "CHANGES_REQUESTED"
        and threads["unresolvedCount"] == 0
        and checks_are_green(checks)
    )
    blockers: list[str] = []
    if pr_data.get("state") != "OPEN":
        blockers.append(f"state is {pr_data.get('state')}")
    if pr_data.get("isDraft"):
        blockers.append("PR is draft")
    if pr_data.get("baseRefName") != "main":
        blockers.append(f"base is {pr_data.get('baseRefName')}, not main")
    if pr_data.get("mergeStateStatus") != "CLEAN":
        blockers.append(f"mergeStateStatus is {pr_data.get('mergeStateStatus')}")
    if pr_data.get("reviewDecision") != "APPROVED" and not stale_review:
        blockers.append(f"reviewDecision is {pr_data.get('reviewDecision')}")
    if threads["unresolvedCount"]:
        blockers.append(f"{threads['unresolvedCount']} unresolved review threads")
    if not checks_are_green(checks):
        blockers.append("not all checks are completed success/skipped")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "staleReviewLikely": stale_review,
        "checks": checks,
    }


def parse_issues(pr_data: dict[str, Any]) -> list[int]:
    text = "\n".join(str(pr_data.get(key) or "") for key in ("title", "headRefName", "body"))
    return sorted({int(match.group(1)) for match in CLOSING_RE.finditer(text)})


def state_file(pr: int, state_dir: Path) -> Path:
    return state_dir / f"pr-{pr}.json"


def save_state(pr: int, state_dir: Path, patch: dict[str, Any]) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_file(pr, state_dir)
    if path.exists():
        state = json.loads(path.read_text())
    else:
        state = {"pr": pr, "createdAt": now_iso(), "events": []}
    state.update({key: value for key, value in patch.items() if key != "event"})
    if "event" in patch:
        state.setdefault("events", []).append({"at": now_iso(), **patch["event"]})
    state["updatedAt"] = now_iso()
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    return state


def perform_merge(pr: int, state_dir: Path) -> dict[str, Any]:
    save_state(pr, state_dir, {"mergeStarted": True, "event": {"phase": "merge-started"}})
    result = run(
        ["gh", "pr", "merge", str(pr), "--repo", REPO, "--squash", "--delete-branch"],
        check=False,
    )
    verification = pr_view(pr)
    merged = verification.get("state") == "MERGED" and verification.get("mergedAt")
    save_state(
        pr,
        state_dir,
        {
            "mergeCommandExit": result.returncode,
            "mergeCommandStdout": result.stdout,
            "mergeCommandStderr": result.stderr,
            "merged": bool(merged),
            "mergedAt": verification.get("mergedAt"),
            "mergeCommit": (verification.get("mergeCommit") or {}).get("oid"),
            "event": {"phase": "merge-verified", "merged": bool(merged)},
        },
    )
    if not merged:
        raise ToolError(f"Merge did not verify as MERGED. gh stderr: {result.stderr}")
    return verification


def git_status_short(cwd: Path = REPO_ROOT) -> str:
    return run(["git", "status", "--short", "--branch"], cwd=cwd).stdout


def ensure_stable_checkout_is_safe() -> None:
    branch = run(["git", "branch", "--show-current"]).stdout
    raw = run(["git", "status", "--porcelain"]).stdout
    changes = [line for line in raw.splitlines() if line]
    disallowed = [line for line in changes if not line.startswith("?? .hermes/")]
    if branch != "main" and changes:
        raise ToolError(
            "Refusing postmerge from a non-main branch with local changes. "
            f"Current branch: {branch}. Changes: {changes}"
        )
    if branch == "main" and disallowed:
        raise ToolError(
            "Refusing postmerge because stable main has local changes outside expected .hermes/. "
            f"Changes: {disallowed}"
        )


def update_main() -> str:
    ensure_stable_checkout_is_safe()
    run(["git", "fetch", "origin", "--prune"])
    run(["git", "checkout", "main"])
    run(["git", "pull", "--ff-only", "origin", "main"])
    return run(["git", "rev-parse", "--short", "HEAD"]).stdout


def worktrees() -> list[dict[str, str]]:
    raw = run(["git", "worktree", "list", "--porcelain"]).stdout
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries


def clean_worktree_for_branch(branch: str) -> dict[str, Any]:
    target_ref = f"refs/heads/{branch}"
    removed: list[str] = []
    skipped: list[dict[str, str]] = []
    for entry in worktrees():
        path = Path(entry.get("worktree", ""))
        if entry.get("branch") != target_ref or path == REPO_ROOT:
            continue
        status = run(["git", "status", "--porcelain"], cwd=path).stdout
        if status:
            skipped.append({"path": str(path), "reason": "worktree has local changes"})
            continue
        run(["git", "worktree", "remove", str(path)])
        removed.append(str(path))
    branch_deleted = False
    branch_exists = (
        run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            check=False,
        ).returncode
        == 0
    )
    if branch_exists:
        run(["git", "branch", "-D", branch])
        branch_deleted = True
    return {
        "removedWorktrees": removed,
        "skippedWorktrees": skipped,
        "branchDeleted": branch_deleted,
    }


def issue_view(issue: int) -> dict[str, Any]:
    return gh_json(
        ["issue", "view", str(issue), "--repo", REPO, "--json", "number,title,state,labels,url"]
    )


def update_issue(issue: int, pr: int) -> dict[str, Any]:
    before = issue_view(issue)
    if before["state"] != "CLOSED":
        run(
            [
                "gh",
                "issue",
                "close",
                str(issue),
                "--repo",
                REPO,
                "--comment",
                f"Merged in PR #{pr}.",
            ]
        )
    edit_args = [
        "issue",
        "edit",
        str(issue),
        "--repo",
        REPO,
        "--add-label",
        DONE_LABEL,
    ]
    for label in ACTIVE_LABELS:
        edit_args.extend(["--remove-label", label])
    run(["gh", *edit_args])
    after = issue_view(issue)
    return {"issue": issue, "before": before, "after": after}


def open_prs() -> list[dict[str, Any]]:
    data = gh_json(
        [
            "pr",
            "list",
            "--repo",
            REPO,
            "--state",
            "open",
            "--limit",
            "50",
            "--json",
            "number,title,headRefName,baseRefName,mergeStateStatus,reviewDecision,url,headRefOid",
        ]
    )
    return data or []


def affected_open_prs(merged_files: set[str]) -> list[dict[str, Any]]:
    affected = []
    for pr in open_prs():
        detail = gh_json(
            ["pr", "view", str(pr["number"]), "--repo", REPO, "--json", "files,commits"]
        )
        pr_files = {item["path"] for item in detail.get("files") or []}
        overlap = sorted(merged_files & pr_files)
        commits = [
            {"oid": item["oid"], "messageHeadline": item.get("messageHeadline")}
            for item in detail.get("commits") or []
        ]
        affected.append({**pr, "overlapFiles": overlap, "commits": commits})
    return affected


def main_runs(head_sha: str) -> list[dict[str, Any]]:
    data = gh_json(
        [
            "run",
            "list",
            "--repo",
            REPO,
            "--branch",
            "main",
            "--limit",
            "20",
            "--json",
            "databaseId,name,status,conclusion,headSha,url,createdAt",
        ]
    )
    return [item for item in data if item.get("headSha") == head_sha]


def wait_for_runs(head_sha: str, timeout_seconds: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    runs = main_runs(head_sha)
    while time.monotonic() < deadline:
        if runs and all(item["status"] == "completed" for item in runs):
            return runs
        time.sleep(10)
        runs = main_runs(head_sha)
    return runs


def health_check() -> dict[str, Any]:
    request = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "getmailean-postmerge"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": response.status == 200, "status": response.status, "body": body}
    except urllib.error.URLError as exc:
        return {"ok": False, "status": None, "body": str(exc)}


def risk_tier(report: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    if report.get("staleReviewLikely"):
        reasons.append("stale review state accepted")
    if report.get("issuesUpdated"):
        reasons.append("issue labels or closure updated")
    affected = report.get("affectedOpenPrs") or []
    dirty = [
        pr
        for pr in affected
        if pr.get("mergeStateStatus") not in {"CLEAN"} or pr.get("overlapFiles")
    ]
    if dirty:
        reasons.append("open PRs need attention after base move")
    if not report.get("health", {}).get("ok"):
        reasons.append("production health failed")
    failed_runs = [
        run
        for run in report.get("mainRuns") or []
        if run.get("status") == "completed" and run.get("conclusion") != "success"
    ]
    if failed_runs:
        reasons.append("main branch CI/CD failure")
    tier = 0
    if reasons:
        tier = 1
    if any("health failed" in reason or "CI/CD failure" in reason for reason in reasons):
        tier = 2
    return {"tier": tier, "reasons": reasons}


def write_handoff(report: dict[str, Any], risk: dict[str, Any]) -> Path | None:
    if risk["tier"] == 0:
        return None
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    pr = report["pr"]["number"]
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    path = HANDOFF_DIR / f"{date}-getmailean-pr{pr}-postmerge.md"
    affected_lines = []
    for item in report.get("affectedOpenPrs") or []:
        overlap = ", ".join(item.get("overlapFiles") or []) or "none"
        affected_lines.append(
            f"- PR #{item['number']} `{item['title']}`: "
            f"{item.get('mergeStateStatus')} / {item.get('reviewDecision')}; overlap: {overlap}"
        )
    issue_lines = []
    for item in report.get("issuesUpdated") or []:
        after = item["after"]
        labels = ", ".join(label["name"] for label in after.get("labels") or [])
        issue_lines.append(f"- Issue #{item['issue']}: {after['state']}; labels: {labels}")
    run_lines = []
    for item in report.get("mainRuns") or []:
        run_lines.append(
            f"- {item['name']}: {item['status']} / {item.get('conclusion')} ({item['url']})"
        )
    content = f"""# getmAIlean PR #{pr} postmerge handoff - {date}

## Summary

- PR: {report["pr"]["url"]}
- Title: `{report["pr"]["title"]}`
- Merge commit: `{report.get("mergeCommit")}`
- Local main: `{report.get("localMain")}`
- Risk tier: {risk["tier"]} ({"; ".join(risk["reasons"]) or "routine"})

## Cleanup

```json
{json.dumps(report.get("cleanup"), indent=2, sort_keys=True)}
```

## Issues

{chr(10).join(issue_lines) or "- None detected."}

## Main runs

{chr(10).join(run_lines) or "- No runs found for merge commit."}

## Production health

```json
{json.dumps(report.get("health"), indent=2, sort_keys=True)}
```

## Open PRs after merge

{chr(10).join(affected_lines) or "- None open."}

## Next safe action

Review any open PR reported as `DIRTY`, `UNSTABLE`, or with overlapping files before merging it.
"""
    path.write_text(content)
    return path


def postmerge(pr: int, state_dir: Path, wait_ci: int, no_handoff: bool) -> dict[str, Any]:
    pr_data = pr_view(pr)
    if pr_data.get("state") != "MERGED":
        raise ToolError(f"PR #{pr} is not MERGED. Current state: {pr_data.get('state')}")
    save_state(pr, state_dir, {"postmergeStarted": True, "event": {"phase": "postmerge-started"}})
    local_main = update_main()
    cleanup = clean_worktree_for_branch(pr_data["headRefName"])
    issue_numbers = parse_issues(pr_data)
    issues_updated = [update_issue(issue, pr) for issue in issue_numbers]
    merge_commit = (pr_data.get("mergeCommit") or {}).get("oid")
    merged_files = {item["path"] for item in pr_data.get("files") or []}
    affected = affected_open_prs(merged_files)
    runs = wait_for_runs(merge_commit, wait_ci) if merge_commit else []
    health = health_check()
    report = {
        "pr": pr_data,
        "mergeCommit": merge_commit,
        "localMain": local_main,
        "cleanup": cleanup,
        "issuesUpdated": issues_updated,
        "affectedOpenPrs": affected,
        "mainRuns": runs,
        "health": health,
        "status": git_status_short(),
    }
    risk = risk_tier(report)
    handoff = None if no_handoff else write_handoff(report, risk)
    report["risk"] = risk
    report["handoff"] = str(handoff) if handoff else None
    save_state(
        pr,
        state_dir,
        {
            "postmergeCompleted": True,
            "risk": risk,
            "handoff": report["handoff"],
            "event": {"phase": "postmerge-completed", "riskTier": risk["tier"]},
        },
    )
    return report


def compact_card(report: dict[str, Any]) -> str:
    pr = report["pr"]
    run_bits = [
        f"{item['name']}={item['status']}/{item.get('conclusion')}"
        for item in report.get("mainRuns") or []
    ]
    affected_bits = [
        f"#{item['number']} {item.get('mergeStateStatus')}/{item.get('reviewDecision')}"
        for item in report.get("affectedOpenPrs") or []
    ]
    return "\n".join(
        [
            f"PR #{pr['number']}: {pr['title']}",
            f"state: {pr.get('state')} mergeCommit: {report.get('mergeCommit')}",
            f"local main: {report.get('localMain')} status: {report.get('status')!r}",
            f"cleanup: {json.dumps(report.get('cleanup'), sort_keys=True)}",
            f"issues updated: {[item['issue'] for item in report.get('issuesUpdated') or []]}",
            f"runs: {', '.join(run_bits) or 'none found'}",
            f"health: {report.get('health')}",
            f"open PRs: {', '.join(affected_bits) or 'none'}",
            f"risk: T{report.get('risk', {}).get('tier')} {report.get('risk', {}).get('reasons')}",
            f"handoff: {report.get('handoff') or 'not written'}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="getmAIlean merge/postmerge helper")
    parser.add_argument("pr", type=int, help="PR number")
    parser.add_argument("--merge", action="store_true", help="squash merge the PR")
    parser.add_argument("--postmerge", action="store_true", help="run postmerge cleanup and checks")
    parser.add_argument(
        "--yes", action="store_true", help="required for mutating merge/postmerge actions"
    )
    parser.add_argument("--wait-ci", type=int, default=180, help="seconds to wait for main runs")
    parser.add_argument("--no-handoff", action="store_true", help="skip risk-tier handoff writing")
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR, help="phase state directory")
    parser.add_argument("--json", action="store_true", help="print JSON instead of compact text")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mutating = args.merge or args.postmerge
    if mutating and not args.yes:
        print("Refusing mutating action without --yes", file=sys.stderr)
        return 2
    pr_data = pr_view(args.pr)
    threads = unresolved_threads(args.pr) if pr_data.get("state") == "OPEN" else {}
    ready = readiness(pr_data, threads) if pr_data.get("state") == "OPEN" else None
    save_state(
        args.pr,
        args.state_dir,
        {
            "lastInspect": now_iso(),
            "prUrl": pr_data.get("url"),
            "headRefName": pr_data.get("headRefName"),
            "event": {"phase": "inspect", "state": pr_data.get("state")},
        },
    )
    if not mutating:
        payload = {"pr": pr_data, "threads": threads, "readiness": ready}
        print(
            json.dumps(payload, indent=2, sort_keys=True) if args.json else compact_inspect(payload)
        )
        return 0
    try:
        if args.merge:
            if not ready or not ready["ready"]:
                print(json.dumps({"readiness": ready}, indent=2), file=sys.stderr)
                return 3
            pr_data = perform_merge(args.pr, args.state_dir)
        report: dict[str, Any] = {"pr": pr_data}
        if args.postmerge:
            report = postmerge(args.pr, args.state_dir, args.wait_ci, args.no_handoff)
    except ToolError as exc:
        save_state(
            args.pr,
            args.state_dir,
            {"lastError": str(exc), "event": {"phase": "error", "message": str(exc)}},
        )
        raise
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else compact_card(report))
    return 0


def compact_inspect(payload: dict[str, Any]) -> str:
    pr = payload["pr"]
    readiness_payload = payload.get("readiness") or {}
    threads = payload.get("threads") or {}
    checks = readiness_payload.get("checks") or check_summary(pr)
    check_bits = [f"{item['name']}={item['status']}/{item['conclusion']}" for item in checks]
    return "\n".join(
        [
            f"PR #{pr['number']}: {pr['title']}",
            f"url: {pr['url']}",
            f"state: {pr['state']} draft: {pr['isDraft']} base: {pr['baseRefName']}",
            f"head: {pr['headRefName']} {pr['headRefOid']}",
            f"merge/review: {pr['mergeStateStatus']} / {pr['reviewDecision']}",
            f"checks: {', '.join(check_bits) or 'none'}",
            f"unresolved threads: {threads.get('unresolvedCount', 'not checked')}",
            f"closing issues: {parse_issues(pr)}",
            f"ready: {readiness_payload.get('ready')} blockers: {readiness_payload.get('blockers')}",
            f"stale review likely: {readiness_payload.get('staleReviewLikely')}",
        ]
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
