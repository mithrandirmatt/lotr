#!/usr/bin/env python3
"""project.py -- project-level automation for the lotr repo."""

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve paths and make pyutils importable without installation
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent   # build/py/
BUILD_DIR  = SCRIPT_DIR.parent                  # build/
REPO_ROOT  = BUILD_DIR.parent                   # <root>/

sys.path.insert(0, str(REPO_ROOT))

from pyutils.utils.utils import pb, psb, pi, psi, pe, pse, pw, psw, pok, psok
from pyutils.utils.ini   import read_ini, get_section
from pyutils.utils       import git

INI_PATH = BUILD_DIR / "build.ini"

_PPK_SRC     = "/root/.ssh/id_rsa.ppk"
_OPENSSH_KEY = "/root/.ssh_keys/id_openssh"


def ensure_ssh_agent():
    """Mirror the 'sa' alias: start ssh-agent, convert .ppk if needed, ssh-add."""
    result = subprocess.run(["ssh-agent", "-s"], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        m = re.match(r'^(SSH_AUTH_SOCK|SSH_AGENT_PID)=([^;]+);', line)
        if m:
            os.environ[m.group(1)] = m.group(2)

    if not os.path.exists(_OPENSSH_KEY):
        pi("Converting PuTTY key to OpenSSH format...")
        subprocess.run(
            ["puttygen", _PPK_SRC, "-O", "private-openssh", "-o", _OPENSSH_KEY,
             "--new-passphrase", "/dev/null"],
            check=True
        )
        os.chmod(_OPENSSH_KEY, 0o600)

    subprocess.run(["ssh-add", _OPENSSH_KEY], check=True)


# ---------------------------------------------------------------------------
# lib submodule helpers
# ---------------------------------------------------------------------------

def _lib_rel_path(abs_path: Path) -> str:
    """Path of a lib relative to REPO_ROOT as a POSIX string (for git)."""
    return abs_path.relative_to(REPO_ROOT).as_posix()


def _is_registered_submodule(rel_path: str) -> bool:
    """Return True if rel_path is already listed in .gitmodules."""
    result = subprocess.run(
        ["git", "submodule", "status", "--", rel_path],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _git_output(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _parse_remote_owner(remote_url: str) -> str:
    # Supports: git@github.com:owner/repo.git and https://github.com/owner/repo(.git)
    m = re.search(r"github\.com[:/]([^/]+)/[^/]+(?:\.git)?$", remote_url)
    return m.group(1).strip().lower() if m else ""


def _is_submodule_path(repo_root: Path, abs_path: Path) -> bool:
    if abs_path == repo_root:
        return False
    try:
        rel = abs_path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return _is_registered_submodule(rel)


def _ensure_lib_submodule(name: str, abs_path: Path) -> bool:
    """Ensure a LIBS entry is a clean git repo registered as a submodule.

    Returns True if ready to proceed, False on any blocking problem.
    """
    if not git.is_git_repo(str(abs_path)):
        pe(f"[{name}] not a git repo — cannot register as submodule.")
        return False

    if git.is_dirty(str(abs_path)):
        pe(f"[{name}] has local modifications at {abs_path}")
        pe(f"  Stash or discard changes before running project_commit.")
        return False

    rel_path = _lib_rel_path(abs_path)

    if _is_registered_submodule(rel_path):
        psi(f"[{name}] already a submodule ({rel_path}) — ok.")
        return True

    remote_url = git.get_remote_url(str(abs_path))
    if not remote_url:
        pe(f"[{name}] no remote URL found — cannot add as submodule.")
        return False

    pb(f"[{name}] registering submodule: {rel_path}  ->  {remote_url}")
    result = subprocess.run(
        ["git", "submodule", "add", "--force", remote_url, rel_path],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pe(f"[{name}] git submodule add failed:\n{result.stderr.strip()}")
        return False

    pok(f"[{name}] registered as submodule.")
    return True


# ---------------------------------------------------------------------------
# commit_project
# ---------------------------------------------------------------------------

def cmd_commit_project(args):
    ensure_ssh_agent()

    cfg   = read_ini(str(INI_PATH))
    repos = get_section(cfg, "REPOS")

    # Ensure every [LIBS] entry is registered as a clean submodule first.
    libs = get_section(cfg, "LIBS")
    if libs:
        pb("Checking LIBS submodules...")
        for name, rel in libs.items():
            abs_path = (BUILD_DIR / rel).resolve()
            if not _ensure_lib_submodule(name, abs_path):
                pe("Aborting — resolve LIBS issues above before committing.")
                sys.exit(1)
        pok("LIBS submodules ok.")

    # Resolve paths relative to BUILD_DIR (where build.ini lives)
    resolved = {name: (BUILD_DIR / rel).resolve() for name, rel in repos.items()}

    # Deeper paths first; root repo (shallowest) commits last
    ordered = sorted(resolved.items(), key=lambda kv: len(kv[1].parts), reverse=True)

    message = input("Commit message: ").strip()
    if not message:
        pe("Commit message cannot be empty.")
        sys.exit(1)

    for name, abs_path in ordered:
        pb(f"[{name}]  {abs_path}")
        if not git.is_git_repo(str(abs_path)):
            pw(f"[{name}] skipped — not a git repo (submodule not initialized?)")
            continue
        if git.is_dirty(str(abs_path)):
            git.stage_all(str(abs_path))
            git.commit(str(abs_path), message)
            git.push(str(abs_path))
        elif git.is_ahead(str(abs_path)):
            psi(f"[{name}] clean but unpushed — pushing...")
            git.push(str(abs_path))
        else:
            psi(f"[{name}] clean — nothing to commit or push.")
            continue
        pok(f"[{name}] done.")

    pok("All repos committed.")

    pb("Git status:")
    subprocess.run(["git", "status"], cwd=str(REPO_ROOT))


def _squash_repo_to_single_commit(repo_path: Path, message: str) -> str:
    branch = _git_output(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        raise RuntimeError("detached HEAD is not supported for squash")

    temp_branch = f"squash-temp-{int(time.time())}"
    _git_output(repo_path, "checkout", "--orphan", temp_branch)
    _git_output(repo_path, "add", "-A")

    commit = subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr.strip() or commit.stdout.strip() or "git commit failed")

    _git_output(repo_path, "branch", "-M", branch)
    return branch


def cmd_squash_project(args):
    cfg = read_ini(str(INI_PATH))
    repos = get_section(cfg, "REPOS")
    if not repos:
        pe("No [REPOS] entries found in build/build.ini")
        sys.exit(1)

    resolved = {name: (BUILD_DIR / rel).resolve() for name, rel in repos.items()}
    root_repo = resolved.get("lotr", REPO_ROOT)

    root_remote = git.get_remote_url(str(root_repo))
    root_owner = _parse_remote_owner(root_remote)
    owner_whitelist = {root_owner} if root_owner else set()

    pb("Selecting repos to squash...")
    if owner_whitelist:
        psi(f"Owner filter: {', '.join(sorted(owner_whitelist))}")
    else:
        pw("Could not infer root GitHub owner; ownership filter disabled.")

    candidates: list[tuple[str, Path]] = []
    for name, abs_path in sorted(resolved.items(), key=lambda kv: len(kv[1].parts), reverse=True):
        if not git.is_git_repo(str(abs_path)):
            pw(f"[{name}] skipped — not a git repo")
            continue

        if _is_submodule_path(root_repo, abs_path):
            psi(f"[{name}] skipped — registered submodule")
            continue

        remote = git.get_remote_url(str(abs_path))
        owner = _parse_remote_owner(remote)
        if owner_whitelist and owner and owner not in owner_whitelist:
            psi(f"[{name}] skipped — remote owner '{owner}' not in whitelist")
            continue

        if owner_whitelist and not owner:
            psi(f"[{name}] skipped — no parseable GitHub owner on remote")
            continue

        candidates.append((name, abs_path))

    if not candidates:
        pe("No eligible repos found to squash.")
        sys.exit(1)

    print("")
    print("Repos selected for squash:")
    for name, abs_path in candidates:
        print(f"  - {name}: {abs_path}")

    print("")
    message = input("Squash commit message: ").strip()
    if not message:
        pe("Commit message cannot be empty.")
        sys.exit(1)

    squashed: list[tuple[str, Path, str]] = []
    for name, abs_path in candidates:
        pb(f"[{name}] squashing history -> single commit")
        try:
            branch = _squash_repo_to_single_commit(abs_path, message)
            pok(f"[{name}] squashed on branch '{branch}'.")
            squashed.append((name, abs_path, branch))
        except Exception as exc:
            pe(f"[{name}] squash failed: {exc}")

    if not squashed:
        pe("No repos were squashed successfully.")
        sys.exit(1)

    print("")
    push_now = input("Push squashed branches now? [y/N]: ").strip().lower()
    if push_now not in {"y", "yes"}:
        psi("Push skipped by user.")
        return

    ensure_ssh_agent()
    for name, abs_path, branch in squashed:
        remote_url = git.get_remote_url(str(abs_path))
        if remote_url.startswith("https://"):
            pw(f"[{name}] skipped push — HTTPS remote configured ({remote_url})")
            continue
        pb(f"[{name}] force-pushing squashed branch '{branch}'...")
        result = subprocess.run(
            ["git", "push", "--force-with-lease", "origin", branch],
            cwd=str(abs_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            pe(f"[{name}] push failed: {result.stderr.strip() or result.stdout.strip()}")
        else:
            pok(f"[{name}] push complete.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Project automation for lotr.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("commit_project", help="Stage, commit, and push all repos in build.ini.")
    sub.add_parser("squash_project", help="Squash eligible project repos to one commit and optionally push.")
    args = parser.parse_args()

    if args.command == "commit_project":
        cmd_commit_project(args)
    elif args.command == "squash_project":
        cmd_squash_project(args)


if __name__ == "__main__":
    main()
