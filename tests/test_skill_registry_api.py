import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from backend import main


class SkillRegistryApiTest(unittest.IsolatedAsyncioTestCase):
    async def get_skills(self) -> httpx.Response:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.get("/api/skills")

    async def test_skills_endpoint_accepts_registered_skill_contracts(self) -> None:
        response = await self.get_skills()

        self.assertEqual(response.status_code, 200)
        skills = {skill["id"]: skill for skill in response.json()}
        self.assertEqual(skills["jarvis"]["status"], "implemented")
        self.assertEqual(skills["jarvis"]["type"], "core")

    async def test_invalid_skill_returns_path_and_writes_validation_log(self) -> None:
        with TemporaryDirectory(dir=main.ROOT_DIR) as directory:
            skill_dir = Path(directory) / "broken"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(
                '{"id": "broken"}', encoding="utf-8"
            )
            with (
                patch.object(main, "SKILLS_DIR", Path(directory)),
                self.assertLogs("backend.main", level="ERROR") as logs,
            ):
                response = await self.get_skills()

        self.assertEqual(response.status_code, 500)
        self.assertIn("broken/skill.json", response.json()["detail"])
        self.assertIn("Invalid skill definition", logs.output[0])
        self.assertIn("validation errors", logs.output[0])


if __name__ == "__main__":
    unittest.main()
