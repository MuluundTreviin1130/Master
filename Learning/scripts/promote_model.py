from __future__ import annotations

import argparse
import contextlib
import json
import os

from Settings import get_settings
from Learning.registry.update_model_status import update_model_status


def _load_settings(overrides: dict | None = None):
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
        return get_settings(overrides=overrides)


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote a Learning model after external validation.")
    parser.add_argument("--family-hash", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--stage", required=True, choices=["candidate", "eligible", "validated", "production"])
    parser.add_argument("--prefer", action="store_true")
    parser.add_argument("--deprefer", action="store_true")
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--deactivate", action="store_true")
    args = parser.parse_args()

    settings = _load_settings()
    is_preferred = True if args.prefer else False if args.deprefer else None
    is_active = True if args.activate else False if args.deactivate else None

    entry, registry_path = update_model_status(
        settings,
        args.family_hash,
        args.model_id,
        validation_stage=args.stage,
        is_active=is_active,
        is_preferred=is_preferred,
    )

    print(
        json.dumps(
            {
                "ok": True,
                "registry_path": registry_path,
                "family_hash": args.family_hash,
                "model_id": args.model_id,
                "validation_stage": entry.get("validation_stage"),
                "is_active": entry.get("is_active"),
                "preferred": bool(args.prefer),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
