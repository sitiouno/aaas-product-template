from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from product_app.quality import (
    TARGET_INTENTS,
    apply_market_intelligence_hardening,
    compare_validation_evidence,
)


DEFAULT_BEFORE = "validation_evidence.json"
DEFAULT_AFTER = "validation_evidence_hardened.json"
DEFAULT_OUT_JSON = "quality_comparison_market_intelligence.json"
DEFAULT_OUT_MD = "quality_comparison_market_intelligence.md"


def build_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# Market Intelligence Quality Comparison")
    lines.append("")
    lines.append(f"Generated: {report.get('generated_at', datetime.now(UTC).isoformat())}")
    lines.append(
        f"Inputs: {report.get('inputs', {}).get('before', DEFAULT_BEFORE)} vs {report.get('inputs', {}).get('after', DEFAULT_AFTER)}"
    )
    lines.append("")

    metric_order = [
        "informational_density",
        "low_redundancy",
        "executive_summary_clarity",
        "explicit_prioritization",
        "why_now_quality",
        "risk_invalidation_quality",
        "watchlist_trigger_quality",
        "structural_consistency",
        "signal_noise",
        "estimated_executive_utility",
        "word_count",
    ]

    for intent, payload in report.get("intents", {}).items():
        lines.append(f"## {intent}")
        if payload.get("missing"):
            lines.append("- Missing in one of the evidence files.")
            lines.append("")
            continue

        lines.append("| Metric | Before | After | Delta |")
        lines.append("|---|---:|---:|---:|")
        before = payload.get("before", {})
        after = payload.get("after", {})
        delta = payload.get("delta", {})
        for metric in metric_order:
            if metric in (before.get("metrics") or {}):
                before_value = float(before["metrics"].get(metric, 0.0))
                after_value = float(after["metrics"].get(metric, 0.0))
            elif metric == "estimated_executive_utility":
                before_value = float(before.get("overall_score", 0.0))
                after_value = float(after.get("overall_score", 0.0))
            else:
                before_value = float(before.get(metric, 0.0))
                after_value = float(after.get(metric, 0.0))

            if metric == "word_count":
                before_value = float(before.get("word_count", 0))
                after_value = float(after.get("word_count", 0))

            delta_value = float(delta.get(metric, after_value - before_value))
            lines.append(f"| {metric} | {before_value:.2f} | {after_value:.2f} | {delta_value:+.2f} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare market_intelligence quality before/after.")
    parser.add_argument("--before", default=DEFAULT_BEFORE)
    parser.add_argument("--after", default=DEFAULT_AFTER)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--simulate-hardening-after",
        action="store_true",
        help="Apply calibrated hardening to 'after' evidence before comparison.",
    )
    args = parser.parse_args()

    before_path = Path(args.before).resolve()
    after_path = Path(args.after).resolve()
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()

    comparison_after_path = after_path
    temporary_after: NamedTemporaryFile[str] | None = None
    if args.simulate_hardening_after:
        after_payload = json.loads(after_path.read_text(encoding="utf-8"))
        for case in after_payload.get("cases", []):
            intent = (case.get("research_intent") or case.get("intent") or "").strip().lower()
            if intent not in TARGET_INTENTS:
                continue
            hardened = apply_market_intelligence_hardening(
                research_intent=intent,
                report_text=str(case.get("final_text") or ""),
            )
            case["final_text"] = str(hardened.get("final_text") or case.get("final_text") or "")

        temporary_after = NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        temporary_after.write(json.dumps(after_payload, ensure_ascii=True))
        temporary_after.flush()
        comparison_after_path = Path(temporary_after.name)

    report = compare_validation_evidence(before_path, comparison_after_path)
    if args.simulate_hardening_after:
        report["simulation"] = {
            "simulate_hardening_after": True,
            "source_after": after_path.name,
        }

    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    out_md.write_text(build_markdown(report), encoding="utf-8")

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")

    if temporary_after is not None:
        temporary_after.close()


if __name__ == "__main__":
    main()
