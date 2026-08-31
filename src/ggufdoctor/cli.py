from __future__ import annotations

import argparse
import json
import sys

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.engines.jinja2_engine import Jinja2Engine
from ggufdoctor.fixtures import load_fixtures
from ggufdoctor.ignorefile import apply_ignores, load_ignores
from ggufdoctor.models import CheckContext
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ggufdoctor",
        description="Lint the chat template embedded in a GGUF file.")
    p.add_argument("target", help="local .gguf path or a Hugging Face repo id")
    p.add_argument("--compare-upstream", metavar="REPO",
                   help="compare rendered output against this source model")
    p.add_argument("--fail-on", choices=["error", "warn", "info", "never"],
                   default="error")
    p.add_argument("--fixtures", metavar="PATH", help="custom fixture corpus JSON")
    p.add_argument("--json", metavar="PATH", dest="json_path")
    p.add_argument("--ignore-file", metavar="PATH", default=".ggufdoctorignore")
    p.add_argument("--require-upstream", action="store_true",
                   help="treat a missing upstream as a failure")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from ggufdoctor.sources import resolve
        model, upstream, coverage = resolve(args.target, args.compare_upstream)
        fixtures = load_fixtures(args.fixtures)
        engines = [Jinja2Engine()]
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream})
        findings = run_sanity_checks(ctx)
        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)
        rules = load_ignores(args.ignore_file)
        findings, suppressed = apply_ignores(findings, rules)
    except Exception as e:  # unreadable input, network failure, bad ignore file
        print(f"ggufdoctor: {e}", file=sys.stderr)
        return 2

    # The checks above may have recorded, on ctx, ids of checks that could
    # not evaluate at all (see models.CheckContext.checks_not_evaluated --
    # e.g. S005/S006 skipping when bos/eos token metadata is missing or out
    # of range). `coverage` was built by resolve() before any check ran, so
    # it knows nothing about that yet. Both report renderers key off
    # `coverage.checks_not_evaluated`, not ctx's copy, so without this merge
    # a model the tool could not fully check would be reported as clean.
    coverage.checks_not_evaluated = list(ctx.checks_not_evaluated)

    print(render_human(model, findings, suppressed, coverage, engines))

    if args.json_path:
        payload = build_json(model, findings, suppressed, coverage, engines)
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=1)

    if args.require_upstream and coverage.upstream not in ("ok",):
        return 1
    return exit_code(findings, args.fail_on)
