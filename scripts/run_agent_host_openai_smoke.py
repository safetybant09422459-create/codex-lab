#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.config import OPENAI_API_KEY
from backend.live_llm_smoke import run_live_llm_smoke


def main() -> int:
    if not OPENAI_API_KEY:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "OPENAI_API_KEY is not configured",
                }
            )
        )
        return 0

    result = run_live_llm_smoke()
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
