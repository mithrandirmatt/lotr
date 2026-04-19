"""Host adapter exposing workspace indexing and search for local agents.

Functions:
 - `repo_browser(path=None, glob=None, max_files=200, read_lines=5)`
 - `code_search(query, max_results=100, case_sensitive=False, regex=False)`
 - `read_file(path)`

These are intentionally minimal implementations intended for local development
and testing. They only read files inside the repository root.
"""
from pathlib import Path
import re
import fnmatch
from typing import List, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_text_file(p: Path) -> bool:
    try:
        # small heuristic: try reading a chunk and decode
        with p.open('rb') as f:
            chunk = f.read(2048)
        if b"\0" in chunk:
            return False
        return True
    except Exception:
        return False


def read_file(path: str) -> str:
    p = (REPO_ROOT / path).resolve()
    if REPO_ROOT not in p.parents and p != REPO_ROOT:
        raise ValueError("path is outside the repository")
    return p.read_text(encoding='utf-8', errors='replace')


def repo_browser(path: Optional[str] = None, glob: Optional[str] = None, max_files: int = 200, read_lines: int = 5) -> List[Dict]:
    """Return a list of files with short snippets.

    - `path`: relative path inside the repo to search from (directory or file).
    - `glob`: optional filename glob (e.g., '*.py').
    """
    base = REPO_ROOT if not path else (REPO_ROOT / path).resolve()
    if REPO_ROOT not in base.parents and base != REPO_ROOT:
        raise ValueError("path is outside the repository")

    files = []
    if base.is_file():
        candidates = [base]
    else:
        candidates = [p for p in base.rglob('*') if p.is_file()]

    results = []
    for p in candidates:
        if len(results) >= max_files:
            break
        if glob and not fnmatch.fnmatch(p.name, glob):
            continue
        if not _is_text_file(p):
            continue
        try:
            with p.open('r', encoding='utf-8', errors='replace') as fh:
                lines = []
                for _ in range(read_lines):
                    line = fh.readline()
                    if not line:
                        break
                    lines.append(line.rstrip('\n'))
        except Exception:
            continue
        results.append({
            'path': str(p.relative_to(REPO_ROOT)),
            'snippet': lines,
            'size': p.stat().st_size,
        })
    return results


def code_search(query: str, max_results: int = 100, case_sensitive: bool = False, regex: bool = False, include_paths: Optional[List[str]] = None) -> List[Dict]:
    """Search repository text files for a query and return matches.

    Returns items: {path, line_no, line, context}
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(query, flags) if regex else None

    scope = [REPO_ROOT]
    if include_paths:
        scope = [(REPO_ROOT / p).resolve() for p in include_paths]

    matches = []
    for base in scope:
        if base.is_file():
            files = [base]
        else:
            files = [p for p in base.rglob('*') if p.is_file()]
        for p in files:
            if not _is_text_file(p):
                continue
            try:
                with p.open('r', encoding='utf-8', errors='replace') as fh:
                    for i, line in enumerate(fh, start=1):
                        hay = line.rstrip('\n')
                        found = False
                        if pattern:
                            if pattern.search(hay):
                                found = True
                        else:
                            if (query in hay) if case_sensitive else (query.lower() in hay.lower()):
                                found = True
                        if found:
                            context = hay
                            matches.append({
                                'path': str(p.relative_to(REPO_ROOT)),
                                'line_no': i,
                                'line': hay,
                                'context': context,
                            })
                            if len(matches) >= max_results:
                                return matches
            except Exception:
                continue
    return matches


if __name__ == '__main__':
    import argparse, json

    parser = argparse.ArgumentParser(description='Host tools: repo_browser & code_search')
    sub = parser.add_subparsers(dest='cmd')
    b = sub.add_parser('browse')
    b.add_argument('--path', default=None)
    b.add_argument('--glob', default=None)
    b.add_argument('--max', type=int, default=200)
    b.add_argument('--lines', type=int, default=5)

    s = sub.add_parser('search')
    s.add_argument('query')
    s.add_argument('--max', type=int, default=100)
    s.add_argument('--regex', action='store_true')

    args = parser.parse_args()
    if args.cmd == 'browse':
        out = repo_browser(path=args.path, glob=args.glob, max_files=args.max, read_lines=args.lines)
        print(json.dumps(out, indent=2))
    elif args.cmd == 'search':
        out = code_search(args.query, max_results=args.max, regex=args.regex)
        print(json.dumps(out, indent=2))
    else:
        parser.print_help()
