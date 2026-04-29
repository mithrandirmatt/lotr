#!/usr/bin/env python3
"""project.py -- project-level automation for the lotr repo."""

import argparse
import os
import re
import subprocess
import sys
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Project automation for lotr.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("commit_project", help="Stage, commit, and push all repos in build.ini.")
    args = parser.parse_args()

    if args.command == "commit_project":
        cmd_commit_project(args)


if __name__ == "__main__":
    main()
