import tempfile
import unittest
from pathlib import Path

from backend.git_workflow import GitWorkflow, _generate_commit_message, redact_secrets


class FakeGit:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def __call__(self, *args, check=True):
        self.calls.append(args)
        if args and args[0] == "commit":
            self.responses[("rev-parse", "HEAD")] = "newhead\n"
        return self.responses.get(args, "")


class GitWorkflowTest(unittest.IsolatedAsyncioTestCase):
    async def test_preflight_blocks_env_database_media_deletion_and_secret(self):
        status = " D old.txt\n?? .env.local\n?? data.db\n?? photo.jpg\n?? token.txt\n"
        fake = FakeGit({
            ("status", "--short"): status,
            ("rev-parse", "HEAD"): "abc123\n",
            ("branch", "--show-current"): "main\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/main\n",
            ("diff", "HEAD", "--", "old.txt", ".env.local", "data.db", "photo.jpg", "token.txt"):
                "diff --git a/token.txt b/token.txt\n--- a/token.txt\n+++ b/token.txt\n"
                "@@ -0,0 +1 @@\n+api_key=verysecretvalue\n",
        })
        with tempfile.TemporaryDirectory() as directory:
            report = await GitWorkflow(fake, Path(directory)).preflight()
        self.assertFalse(report.ok)
        reasons = " ".join(report.blockers)
        for expected in ("Deleted", "Environment", "Database or media", "possible secret"):
            self.assertIn(expected, reasons)

    async def test_secret_finding_has_location_masked_text_and_remediation(self):
        fake = FakeGit({
            ("status", "--short"): " M config.py\n",
            ("rev-parse", "HEAD"): "abc123\n",
            ("branch", "--show-current"): "main\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"):
                "origin/main\n",
            ("diff", "HEAD", "--", "config.py"):
                "diff --git a/config.py b/config.py\n--- a/config.py\n+++ b/config.py\n"
                "@@ -3,1 +3,2 @@\n safe = True\n+api_key = supersecretvalue\n",
        })
        with tempfile.TemporaryDirectory() as directory:
            report = await GitWorkflow(fake, Path(directory)).preflight()
        finding = report.findings[0]
        self.assertEqual((finding.rule, finding.file, finding.line),
                         ("credential-assignment", "config.py", 4))
        self.assertEqual(finding.detected_text, "api_key = [REDACTED]")
        self.assertNotIn("supersecretvalue", repr(report.as_dict()))
        self.assertTrue(finding.remediation)

    async def test_ignore_once_only_allows_current_secret_findings(self):
        status = " M config.py\n"
        diff = ("diff --git a/config.py b/config.py\n--- a/config.py\n+++ b/config.py\n"
                "@@ -1 +1 @@\n-old\n+token=supersecretvalue\n")
        responses = {
            ("status", "--short"): status,
            ("rev-parse", "HEAD"): "oldhead\n",
            ("branch", "--show-current"): "main\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/main\n",
            ("diff", "HEAD", "--", "config.py"): diff,
            ("diff", "--cached", "--name-only", "-z"): "config.py\0",
            ("diff", "--cached", "--", "config.py"): diff,
        }
        fake = FakeGit(responses)
        with tempfile.TemporaryDirectory() as directory:
            workflow = GitWorkflow(fake, Path(directory))
            preflight = await workflow.preflight()
            responses[("rev-parse", "HEAD^")] = "oldhead\n"
            responses[("push", "--porcelain")] = "done\n"
            result = await workflow.commit_push(
                preflight.snapshot, [preflight.findings[0].id]
            )
        self.assertTrue(result["ok"])

    async def test_commit_push_rechecks_snapshot_and_verifies_parent_before_push(self):
        status = " M backend/main.py\n M frontend/index.html\n"
        responses = {
            ("status", "--short"): status,
            ("rev-parse", "HEAD"): "oldhead\n",
            ("branch", "--show-current"): "main\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/main\n",
            ("diff", "HEAD", "--", "backend/main.py", "frontend/index.html"): "+safe change\n",
            ("diff", "--stat", "HEAD"): " 2 files changed\n",
            ("diff", "--cached", "--name-only", "-z"): "backend/main.py\0frontend/index.html\0",
        }
        fake = FakeGit(responses)
        with tempfile.TemporaryDirectory() as directory:
            workflow = GitWorkflow(fake, Path(directory))
            preflight = await workflow.preflight()
            responses[("rev-parse", "HEAD^")] = "oldhead\n"
            responses[("push", "--porcelain")] = "done\n"
            result = await workflow.commit_push(preflight.snapshot)
        self.assertTrue(result["ok"])
        self.assertEqual(result["commit_hash"], "newhead")
        self.assertIn(("commit", "-m", "feat: add safe commit and push workflow"), fake.calls)
        self.assertEqual(fake.calls[-1], ("push", "--porcelain"))

    async def test_changed_snapshot_stops_before_add(self):
        fake = FakeGit({
            ("status", "--short"): " M README.md\n",
            ("rev-parse", "HEAD"): "head\n",
            ("branch", "--show-current"): "main\n",
            ("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"): "origin/main\n",
            ("diff", "HEAD", "--", "README.md"): "+safe\n",
        })
        with tempfile.TemporaryDirectory() as directory:
            result = await GitWorkflow(fake, Path(directory)).commit_push("0" * 64)
        self.assertFalse(result["ok"])
        self.assertNotIn(("add", "--", "README.md"), fake.calls)

    def test_docs_message_is_conventional(self):
        self.assertEqual(
            _generate_commit_message([(" M", "README.md"), ("??", "AGENTS.md")]),
            "docs: update project guidance",
        )

    def test_diff_redaction_never_returns_detected_secret(self):
        redacted = redact_secrets("+token=supersecretvalue\n+safe=True\n")
        self.assertEqual(redacted, "+token=[REDACTED]\n+safe=True\n")
        self.assertNotIn("supersecretvalue", redacted)


if __name__ == "__main__":
    unittest.main()
