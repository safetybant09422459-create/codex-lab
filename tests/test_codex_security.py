import os
import unittest
from unittest.mock import patch

from backend import codex_api


class CodexSubprocessSecurityTest(unittest.TestCase):
    def test_subprocess_environment_uses_allowlist_and_excludes_secrets(self) -> None:
        parent_environment = {
            "PATH": "/usr/bin",
            "HOME": "/home/jarvis",
            "LANG": "C.UTF-8",
            "TERM": "xterm-256color",
            "CODEX_HOME": "/home/jarvis/.codex",
            "OPENAI_API_KEY": "dummy-openai-value",
            "IMMICH_API_KEY": "dummy-immich-value",
            "JARVIS_DEVELOPER_TOKEN": "dummy-developer-value",
            "JARVIS_PRODUCTION_SECRET": "dummy-production-value",
        }
        with patch.dict(os.environ, parent_environment, clear=True):
            child_environment = codex_api.codex_subprocess_env()

        self.assertEqual(
            child_environment,
            {
                "PATH": "/usr/bin",
                "HOME": "/home/jarvis",
                "LANG": "C.UTF-8",
                "TERM": "xterm-256color",
                "CODEX_HOME": "/home/jarvis/.codex",
            },
        )
        excluded = set(parent_environment) - set(codex_api.CODEX_ENV_ALLOWLIST)
        self.assertFalse(excluded & set(child_environment))


if __name__ == "__main__":
    unittest.main()
