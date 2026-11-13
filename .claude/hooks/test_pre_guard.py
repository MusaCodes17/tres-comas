"""Tests for pre_guard.py. Run: python3 -m unittest discover -s .claude/hooks -p 'test_*.py'"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pre_guard  # noqa: E402

ROOT = HERE.parents[1]


def edit(rel: str, content: str = "", tool: str = "Write") -> dict:
    key = "content" if tool == "Write" else "new_string"
    return {"tool_name": tool, "cwd": str(ROOT),
            "tool_input": {"file_path": str(ROOT / rel), key: content}}


def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "cwd": str(ROOT), "tool_input": {"command": cmd}}


def kind(data: dict) -> str | None:
    d = pre_guard.decide(data)
    return d[0] if d else None


class EditRules(unittest.TestCase):
    def setUp(self):
        pre_guard.on_origin_main = lambda root, rel: True

    def test_env_denied_examples_allowed(self):
        self.assertEqual(kind(edit(".env", "X=1")), "deny")
        self.assertEqual(kind(edit("deploy/.env.production", "X=1")), "deny")
        self.assertIsNone(kind(edit("backend/.env.example", "ANTHROPIC_API_KEY=")))

    def test_db_and_data_dir_denied(self):
        self.assertEqual(kind(edit("backend/ledger.db")), "deny")
        self.assertEqual(kind(edit("backend/ledger.db.bak-t2")), "deny")
        self.assertEqual(kind({"tool_name": "Write", "cwd": str(ROOT),
                               "tool_input": {"file_path": "/root/tres-comas-data/x.json", "content": ""}}), "deny")

    def test_real_exports_denied_fixtures_allowed(self):
        self.assertEqual(kind(edit("imports/activity-2026.csv", "a,b")), "deny")
        self.assertIsNone(kind(edit("backend/tests/fixtures/wealthsimple/activity_synthetic.csv", "a,b")))

    def test_broker_hosts_denied_in_code_not_docs(self):
        self.assertEqual(kind(edit("backend/app/connections/providers/x.py", 'URL = "https://production.plaid.com"')), "deny")
        self.assertEqual(kind(edit("backend/app/services/sync.py", "api.wealthsimple.com/v1", tool="Edit")), "deny")
        self.assertIsNone(kind(edit("docs/notes.md", "we never call plaid.com")))
        self.assertIsNone(kind(edit("backend/app/importers/wealthsimple.py", "class WealthsimpleAdapter: ...")))

    def test_mcp_cannot_import_ledger(self):
        self.assertEqual(kind(edit("backend/app/mcp_server/proposals.py", "from app.services.ledger import record_transaction")), "deny")
        self.assertIsNone(kind(edit("backend/app/mcp_server/proposals.py", "from app.services import proposals")))

    def test_float_on_money_path_asks(self):
        self.assertEqual(kind(edit("backend/app/models/models.py", "close = Column(Float)")), "ask")
        self.assertEqual(kind(edit("backend/app/services/positions.py", "def f(q: float): ...")), "ask")
        self.assertIsNone(kind(edit("backend/app/services/positions.py", "q = Decimal('1.25')")))

    def test_raw_http_outside_connections_asks(self):
        self.assertEqual(kind(edit("backend/app/services/market.py", "import httpx\n")), "ask")
        self.assertIsNone(kind(edit("backend/app/connections/client.py", "import httpx\n")))

    def test_auth_and_deploy_ask(self):
        self.assertEqual(kind(edit("backend/app/middleware/auth.py", "x = 1")), "ask")
        self.assertEqual(kind(edit("backend/app/services/tokens.py", "x = 1")), "ask")
        self.assertEqual(kind(edit("deploy/Caddyfile", "x")), "ask")
        self.assertEqual(kind(edit(".github/workflows/ci.yml", "x")), "ask")

    def test_applied_migration_asks(self):
        self.assertEqual(kind(edit("backend/alembic/versions/abc_init.py", "x = 1")), "ask")
        pre_guard.on_origin_main = lambda root, rel: False
        self.assertIsNone(kind(edit("backend/alembic/versions/abc_init.py", "x = 1")))

    def test_plain_edit_allowed(self):
        self.assertIsNone(kind(edit("backend/app/services/exposure.py", "def exposure(): ...")))


class BashRules(unittest.TestCase):
    def test_env_read_denied(self):
        self.assertEqual(kind(bash("cat .env")), "deny")
        self.assertEqual(kind(bash("grep KEY deploy/.env.production")), "deny")
        self.assertIsNone(kind(bash("cat backend/.env.example")))

    def test_broker_host_denied(self):
        self.assertEqual(kind(bash("curl https://api.wealthsimple.com/accounts")), "deny")

    def test_db_writes_ask_reads_allowed(self):
        self.assertEqual(kind(bash("sqlite3 data/ledger.db 'delete from transaction'")), "ask")
        self.assertEqual(kind(bash("rm data/ledger.db")), "ask")
        self.assertIsNone(kind(bash("sqlite3 -readonly data/ledger.db 'select 1'")))

    def test_destructive_ops_ask(self):
        self.assertEqual(kind(bash("cd backend && alembic downgrade -1")), "ask")
        self.assertEqual(kind(bash("docker compose down -v")), "ask")
        self.assertEqual(kind(bash("git push origin main")), "ask")
        self.assertEqual(kind(bash("git push --force origin feature")), "ask")

    def test_feature_push_allowed(self):
        self.assertIsNone(kind(bash("git push -u origin claude/nice-darwin-p5e56r")))
        self.assertIsNone(kind(bash("python -m pytest -q")))


class FailOpen(unittest.TestCase):
    def test_garbage_input(self):
        self.assertIsNone(pre_guard.decide({"tool_name": "Write", "tool_input": "nope"}))
        self.assertIsNone(pre_guard.decide({}))


if __name__ == "__main__":
    unittest.main()
