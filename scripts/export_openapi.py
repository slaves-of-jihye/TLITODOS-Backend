"""Regenerate the checked-in frontend API contract without starting the server."""

import json
from pathlib import Path

from app.main import app


def main():
    destination = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"
    destination.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
