"""Local CLI runner for Product Name."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import load_settings
from .service import run_product_app


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Product Name pipeline locally.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Company name or URL to analyze.",
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Optional user id override.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional session id override.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    if not prompt:
        prompt = input("Prompt: ").strip()
    if not prompt:
        raise SystemExit("A prompt is required.")

    result = asyncio.run(
        run_product_app(
            prompt,
            user_id=args.user_id,
            session_id=args.session_id,
        )
    )

    if result.error:
        raise SystemExit(result.error)

    print(f"Session: {result.session_id}")
    print()
    print(result.final_text or "(No final response text was returned.)")
    print()
    if result.artifacts:
        settings = load_settings()
        print("Generated files:")
        for artifact in result.artifacts:
            print(f"- {Path(settings.output_dir) / artifact['name']}")
    else:
        print("No new local artifacts were detected.")


if __name__ == "__main__":
    main()
