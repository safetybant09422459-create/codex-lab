import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.domain_provider import OperationContext
from backend.gift_executor import GiftProvider
from backend.gift_repository import GiftRepository
from backend.gift_storage import SQLiteGiftStorage
from backend.executors import ExecutorRegistry
from backend.gift_executor import GiftExecutor
from backend.provider_registry import ProviderRegistry
from backend.runtime import RuntimeService


class GiftSkillTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "gift.db"
        self.storage = SQLiteGiftStorage(self.db_path)
        self.repository = GiftRepository(self.storage)
        self.provider = GiftProvider(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_migration_creates_versioned_schema_without_other_databases(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            version = conn.execute("SELECT version FROM gift_schema_migrations").fetchone()[0]
            table = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gift_entries'").fetchone()
        finally:
            conn.close()
        self.assertEqual(version, 1)
        self.assertEqual(table[0], "gift_entries")

    def test_candidate_and_history_can_be_recorded_and_filtered(self) -> None:
        self.repository.create_entry(entry_type="candidate", title="図鑑", recipient="子ども")
        self.repository.create_entry(
            entry_type="given",
            title="花束",
            giver="自分",
            recipient="家族",
            gift_date="2025-05-01",
            amount_yen=3000,
            related_event="記念日",
        )
        entries = self.repository.list_entries(person="家族", year=2025)
        self.assertEqual([entry["title"] for entry in entries], ["花束"])
        self.assertEqual(entries[0]["amount_yen"], 3000)

    def test_given_and_received_require_people_and_date(self) -> None:
        with self.assertRaisesRegex(ValueError, "require giver"):
            self.repository.create_entry(entry_type="received", title="お菓子")

    def test_provider_exposes_read_observation_without_interpretation(self) -> None:
        self.repository.create_entry(entry_type="candidate", title="本")
        operation = OperationContext("list_gifts", "gift", "read", "low")
        result = self.provider.execute(operation, {})
        observation = self.provider.observation_details(operation, result)
        self.assertEqual(observation["facts"]["count"], 1)
        self.assertNotIn("recommendation", observation["facts"])
        self.assertEqual(self.provider.get_execution_mode(operation), "local_gift_read")

    def test_runtime_requires_admin_confirmation_for_write(self) -> None:
        providers = ProviderRegistry()
        providers.register(self.provider)
        executors = ExecutorRegistry()
        executors.register_skill("gift", GiftExecutor(self.provider))
        runtime = RuntimeService(provider_registry=providers, executor_registry=executors)

        denied = runtime.execute_provider_operation(
            "gift", "create_gift", {"entry_type": "candidate", "title": "本"}, role="family", confirmed=True
        )
        blocked = runtime.execute_provider_operation(
            "gift", "create_gift", {"entry_type": "candidate", "title": "本"}, role="admin", confirmed=False
        )
        created = runtime.execute_provider_operation(
            "gift", "create_gift", {"entry_type": "candidate", "title": "本"}, role="admin", confirmed=True
        )

        self.assertTrue(denied["permission_denied"])
        self.assertTrue(blocked["blocked"])
        self.assertTrue(created["success"])
        self.assertEqual(created["execution_mode"], "local_gift_write")


if __name__ == "__main__":
    unittest.main()
