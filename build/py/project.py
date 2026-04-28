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
# commit_project
# ---------------------------------------------------------------------------

def cmd_commit_project(args):
    ensure_ssh_agent()

    cfg   = read_ini(str(INI_PATH))
    repos = get_section(cfg, "REPOS")

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
