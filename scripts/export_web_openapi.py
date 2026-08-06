from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def export_openapi(output: Path) -> None:
    from apps.api.main import app

    content = json.dumps(
        app.openapi(),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        indent=2,
    ) + "\n"
    output.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        export_openapi(args.output)
    except (OSError, TypeError, ValueError) as error:
        print(f"OpenAPI export failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
