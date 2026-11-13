"""PreToolUse guard for Tres Comas' Claude Code sessions.

Job: turn the invariants that a tool call can break mechanically into hard
stops (deny) or deliberate checkpoints (ask), before the edit or command runs.
Canonical rules live in ``docs/invariants.md``; this file is one of their guards.

Deny (refused outright):
- secrets: any ``.env`` / ``.env.*`` except the tracked ``*.example`` templates,
  and shell commands that would print or copy one (INV-3);
- live data: ``*.db`` / ``*.sqlite`` files and anything under ``tres-comas-data/``;
- real broker exports: ``*.csv`` / ``*.xlsx`` written inside the repo outside
  ``backend/tests/fixtures/`` (fixtures must be synthetic);
- broker / account-aggregator hosts in code or shell commands (INV-1, INV-5);
- the MCP server importing the ledger write path (INV-6).

Ask (Musa is prompted):
- floats on money paths: ``Float`` / ``float(`` / ``: float`` in models, services,
  importers or connections (INV-9);
- raw HTTP clients imported outside ``backend/app/connections/`` (INV-7);
- auth, token, session or deploy files (spec working rule: confirm before
  anything auth-related);
- editing an applied migration (one already on ``origin/main``);
- ``alembic downgrade``, writes to a ``.db`` via shell, destroying Docker
  volumes, force pushes and pushes to ``main`` (which deploys).

Rationale / constraints:
- Stdlib only, Python 3.10+, no project venv needed.
- Deny rules run before ask rules; the first match wins.
- Docs (``*.md``) and ``.claude/`` itself are exempt from the content scans, so
  the spec, the docs and this guard can name the hosts they forbid.
- Fails open: any unexpected error prints nothing and exits 0, because a
  developer guard must never wedge a session. CI and tests are the real gate.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit"})

ENV_RE = re.compile(r"^\.env(\..+)?$")
ENV_ALLOWED = frozenset({".env.example", ".env.production.example"})
DB_FILE_RE = re.compile(r"\.(db|sqlite3?)($|[.-])")
DATA_DIR = "tres-comas-data"
EXPORT_RE = re.compile(r"\.(csv|xlsx|xls)$", re.IGNORECASE)
FIXTURES_REL = "backend/tests/fixtures/"
MIGRATIONS_REL = "backend/alembic/versions"

# Broker and account-aggregator endpoints (INV-1, D-1, D-3). Matching a host is
# enough: there is no legitimate reason for app code to name one.
BROKER_HOST_RE = re.compile(
    r"(api\.wealthsimple|wealthsimple\.com/(api|graphql|oauth)|my\.wealthsimple\.com"
    r"|plaid\.com|snaptrade|flinks|yodlee|finicity|\bmx\.com|saltedge|truelayer"
    r"|teller\.io|akoya|moneykit|questrade\.com|iq\.questrade|interactivebrokers"
    r"|ibkr\.com|alpaca\.markets|tradier\.com|schwabapi|tdameritrade|robinhood\.com"
    r"|disnat|qtrade\.ca|tdwebbroker)",
    re.IGNORECASE,
)
CODE_SUFFIXES = frozenset(
    {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml",
     ".cfg", ".ini", ".sh", ".html", ".example", ".txt", ""}
)

MONEY_DIRS = (
    "backend/app/models/", "backend/app/services/",
    "backend/app/importers/", "backend/app/connections/",
)
FLOAT_RE = re.compile(r"\bFloat\b|\bfloat\s*\(|[:>]\s*float\b|\bREAL\b")
HTTP_IMPORT_RE = re.compile(
    r"^\s*(import|from)\s+(requests|httpx|aiohttp|urllib3|urllib\.request)\b"
    r"|^\s*from\s+urllib\s+import\s+request\b",
    re.MULTILINE,
)
MCP_REL = "backend/app/mcp_server/"
LEDGER_WRITE_RE = re.compile(
    r"services\.ledger|from\s+\S*services\s+import\s+[^\n]*\bledger\b|record_transaction"
)
SENSITIVE_PATH_RE = re.compile(
    r"^(backend/app/.*(auth|token|session|oauth|login)[^/]*\.py"
    r"|backend/app/middleware/.*|deploy/.*|docker-compose\.ya?ml|\.github/workflows/.*)$",
    re.IGNORECASE,
)

ENV_READ_RE = re.compile(
    r"\b(cat|less|more|head|tail|bat|strings|xxd|od|grep|rg|sed|awk|cp|scp|rsync|base64|source)\b"
    r"[^|;&\n]*(^|[\s/'\"])\.env(?!\.example|\.production\.example)(\.[\w-]+)?\b"
)
DB_IN_CMD_RE = re.compile(r"\S+\.(db|sqlite3?)\b")
DB_WRITE_RE = re.compile(
    r"\b(delete|update|insert|drop|alter|replace|vacuum)\b|\b(rm|mv|truncate|shred)\b|>\s*\S+\.(db|sqlite)",
    re.IGNORECASE,
)
DOWNGRADE_RE = re.compile(r"\balembic\b.*\bdowngrade\b")
PUSH_RE = re.compile(r"\bgit\s+push\b")
PUSH_MAIN_RE = re.compile(r"\bgit\s+push\b.*(\s|:|/)(main|master)\b")
FORCE_RE = re.compile(r"\s(--force(-with-lease)?|-f)\b")
VOLUME_RE = re.compile(r"\bdocker(-|\s+)compose\b.*\bdown\b.*\s-v\b|\bdocker\s+volume\s+(rm|prune)\b")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _git(cwd: str | None, *args: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=cwd or os.getcwd(), capture_output=True,
            text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return proc.returncode, proc.stdout.strip()


def repo_root(cwd: str | None) -> Path | None:
    """Top of the git tree containing ``cwd``; None outside a repo."""
    rc, out = _git(cwd, "rev-parse", "--show-toplevel")
    return Path(out) if rc == 0 and out else None


def on_origin_main(root: Path, rel: str) -> bool:
    """True if ``rel`` exists on ``origin/main``. Module-level so tests can stub it."""
    rc, _ = _git(str(root), "cat-file", "-e", f"origin/main:{rel}")
    return rc == 0


def _rel(root: Path | None, path: str) -> str | None:
    if root is None:
        return None
    try:
        return Path(os.path.abspath(path)).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _new_text(tool: str, ti: dict) -> str:
    """All text the edit would introduce."""
    if tool == "Write":
        return str(ti.get("content") or "")
    if tool == "Edit":
        return str(ti.get("new_string") or "")
    if tool == "MultiEdit":
        return "\n".join(str(e.get("new_string") or "") for e in ti.get("edits") or [] if isinstance(e, dict))
    return ""


# --------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------

def _decide_edit(data: dict, tool: str, ti: dict) -> tuple[str, str] | None:
    raw = ti.get("file_path")
    if not isinstance(raw, str) or not raw:
        return None
    path = os.path.expanduser(raw)
    p = Path(path)
    base = p.name

    # ---- deny: by path --------------------------------------------------
    if ENV_RE.match(base) and base not in ENV_ALLOWED:
        return ("deny", f"{base} holds secrets (INV-3). Agents never edit or read it; "
                        "Musa edits it by hand. Update the matching .env*.example with key NAMES only.")
    if DB_FILE_RE.search(base) or DATA_DIR in Path(os.path.normpath(path)).parts:
        return ("deny", f"{raw} is live ledger data or a backup. Write through the services "
                        "(ledger.record_transaction), never to the file.")

    root = repo_root(data.get("cwd"))
    rel = _rel(root, path)

    if rel is not None and EXPORT_RE.search(base) and not rel.startswith(FIXTURES_REL):
        return ("deny", f"{rel}: broker exports contain real financial data and never go in the repo. "
                        f"Synthetic fixtures belong under {FIXTURES_REL}.")

    text = _new_text(tool, ti)
    scanned = rel is not None and not rel.startswith(".claude/") and p.suffix != ".md"
    if scanned and (p.suffix in CODE_SUFFIXES or base.startswith(".env")):
        m = BROKER_HOST_RE.search(text)
        if m:
            return ("deny", f"'{m.group(0)}' is a broker or account-aggregator endpoint. "
                            "Tres Comas never calls one (INV-1, INV-5, D-1). Reopening this means revisiting D-1.")

    if rel is not None and rel.startswith(MCP_REL) and LEDGER_WRITE_RE.search(text):
        return ("deny", "The MCP server must not reach the ledger write path (INV-6). "
                        "External clients only create proposals via services.proposals.create.")

    # ---- ask --------------------------------------------------------------
    if rel is not None and rel.startswith(MONEY_DIRS) and FLOAT_RE.search(text):
        return ("ask", f"{rel}: a float type appears on a money path. Money and quantities are "
                       "Decimal with an explicit currency (INV-9, P-1). Confirm this is not storing money.")

    if rel is not None and rel.startswith("backend/app/") and not rel.startswith("backend/app/connections/") \
            and HTTP_IMPORT_RE.search(text):
        return ("ask", f"{rel} imports an HTTP client outside backend/app/connections/. Every outbound "
                       "call must go through the registry and be logged (INV-7).")

    if rel is not None and SENSITIVE_PATH_RE.match(rel):
        return ("ask", f"{rel} is auth, token, deploy or CI configuration. The working rules require "
                       "confirming with Musa before anything auth-related or outward-facing.")

    if (
        rel is not None
        and Path(rel).parent.as_posix() == MIGRATIONS_REL
        and rel.endswith(".py")
        and on_origin_main(root, rel)  # type: ignore[arg-type]
    ):
        return ("ask", f"{rel} is an applied migration on origin/main. Write a new migration instead.")
    return None


def _decide_bash(ti: dict) -> tuple[str, str] | None:
    cmd = ti.get("command")
    if not isinstance(cmd, str) or not cmd:
        return None

    if ENV_READ_RE.search(cmd):
        return ("deny", "This command would print or copy a .env file. Secrets never reach a client, "
                        "Claude included (INV-3). Check key names in the .env*.example templates instead.")
    m = BROKER_HOST_RE.search(cmd)
    if m:
        return ("deny", f"'{m.group(0)}' is a broker or account-aggregator endpoint (INV-1, D-1).")

    if DB_IN_CMD_RE.search(cmd):
        write_like = ("sqlite3" in cmd and "-readonly" not in cmd) or DB_WRITE_RE.search(cmd)
        if write_like:
            return ("ask", "This command can write, move or delete a database file. Transactions are "
                           "append-only (INV-2). Reads should use sqlite3 -readonly.")
    if DOWNGRADE_RE.search(cmd):
        return ("ask", "alembic downgrade reverses a migration and can drop ledger data. Confirm it is intended.")
    if VOLUME_RE.search(cmd):
        return ("ask", "This removes Docker volumes, which hold the live ledger. Confirm, and check the backup first.")
    if PUSH_RE.search(cmd) and FORCE_RE.search(cmd):
        return ("ask", "Force push rewrites remote history. Confirm with Musa.")
    if PUSH_MAIN_RE.search(cmd):
        return ("ask", "Pushing to main deploys to Hetzner (push-to-main deploy). Confirm with Musa.")
    return None


def decide(data: dict) -> tuple[str, str] | None:
    """Return ``("deny"|"ask", reason)`` for a risky tool call, or None to allow."""
    tool = data.get("tool_name")
    ti = data.get("tool_input")
    if not isinstance(ti, dict):
        return None
    if tool in EDIT_TOOLS:
        return _decide_edit(data, tool, ti)
    if tool == "Bash":
        return _decide_bash(ti)
    return None


def main() -> int:
    """Print the hook decision JSON for a risky call; print nothing when allowed. Always exit 0."""
    try:
        data = json.loads(sys.stdin.read() or "{}")
        decision = decide(data) if isinstance(data, dict) else None
        if decision is not None:
            kind, reason = decision
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": kind,
                    "permissionDecisionReason": reason,
                }
            }))
    except Exception:  # fail open: a guard bug must never block the session
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
