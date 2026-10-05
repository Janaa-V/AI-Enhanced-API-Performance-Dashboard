"""Write the API's OpenAPI schema to frontend/openapi.json.

The frontend generates its TypeScript types from that file, so it is the contract between
the two. It is committed, which lets the frontend build without a running backend; CI runs
the check mode so a schema change cannot be merged without the new snapshot.

    uv run python -m scripts.export_openapi           # write the snapshot
    uv run python -m scripts.export_openapi --check   # exit 1 if the snapshot is out of date
"""

import argparse
import json
import sys

from app.config import BACKEND_ROOT
from app.main import app

SNAPSHOT = BACKEND_ROOT.parent / "frontend" / "openapi.json"


def render_schema() -> str:
    # Stable output (fixed indent, keys in FastAPI's order, trailing newline) keeps diffs small.
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the API schema to frontend/openapi.json.")
    parser.add_argument(
        "--check", action="store_true", help="compare with the snapshot instead of writing it"
    )
    args = parser.parse_args(argv)
    schema = render_schema()
    relative = SNAPSHOT.relative_to(BACKEND_ROOT.parent)

    if args.check:
        current = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.exists() else None
        if current != schema:
            print(f"{relative} is out of date. Run `make openapi` in backend/.", file=sys.stderr)
            return 1
        print(f"{relative} is up to date.")
        return 0

    SNAPSHOT.write_text(schema, encoding="utf-8")
    print(f"Wrote {relative}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
