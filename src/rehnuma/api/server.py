"""rehnuma-api: run the API. PORT defaults to 7860 (Hugging Face Spaces).

  uv sync --extra api
  uv run rehnuma-api                 # http://localhost:7860/docs
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    from rehnuma.api.app import create_app
    from rehnuma.llm.client import load_dotenv

    load_dotenv()
    uvicorn.run(create_app(), host=os.environ.get("HOST", "0.0.0.0"),
                port=int(os.environ.get("PORT", "7860")))


if __name__ == "__main__":
    main()
