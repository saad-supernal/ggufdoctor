from __future__ import annotations

import argparse
import json
import os
import sys

from ggufdoctor.checks.reference import run_reference_checks
from ggufdoctor.checks.sanity import run_sanity_checks
from ggufdoctor.fixtures import load_corpus
from ggufdoctor.ignorefile import apply_ignores, load_ignores
from ggufdoctor.models import CheckContext
from ggufdoctor.report.human import render_human
from ggufdoctor.report.json_report import build_json, exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ggufdoctor",
        description="Lint the chat template embedded in a GGUF file.",
        epilog="Also available: `ggufdoctor survey [--top N] [--per-org N] "
               "[--out PATH] [--markdown PATH]`, which surveys chat-template "
               "divergence across the GGUF ecosystem on Hugging Face rather "
               "than linting a single file. Run `ggufdoctor survey --help` "
               "for its own options. (If you have a local file or repo "
               "literally named `survey`, this still lints it as normal --"
               " see is_repo_id/`resolve` for how a target is told apart "
               "from the subcommand.)")
    p.add_argument("target", help="local .gguf path or a Hugging Face repo id")
    p.add_argument("--compare-upstream", metavar="REPO",
                   help="compare rendered output against this source model")
    p.add_argument("--fail-on", choices=["error", "warn", "info", "never"],
                   default="error",
                   help="minimum severity that makes the process exit 1 "
                        "(default: error)")
    p.add_argument("--fixtures", metavar="PATH", help="custom fixture corpus JSON")
    p.add_argument("--json", metavar="PATH", dest="json_path",
                   help="write the full machine-readable report to PATH")
    p.add_argument("--ignore-file", metavar="PATH", default=".ggufdoctorignore",
                   help="path to a file listing finding ids/fixtures to "
                        "suppress (default: .ggufdoctorignore)")
    p.add_argument("--require-upstream", action="store_true",
                   help="fail (exit 1) if the upstream comparison requested "
                        "via --compare-upstream could not be resolved "
                        "(gated, not found, or otherwise unreachable); "
                        "requires --compare-upstream")
    p.add_argument("--runtime", metavar="OLLAMA",
                   help="path to a real `ollama` binary; creates a temporary "
                        "model from the GGUF and renders every fixture through "
                        "Ollama itself (RT001). Needs a running Ollama server "
                        "(OLLAMA_HOST or http://127.0.0.1:11434). Local .gguf "
                        "targets only.")
    p.add_argument("--engines", metavar="NAMES",
                   help="comma-separated engines to run (default: all available; "
                        "choose from jinja2, llama.cpp). jinja2 is the reference "
                        "engine and cannot be deselected.")
    return p


def _build_survey_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ggufdoctor survey",
        description="Survey chat-template divergence from upstream across "
                     "the GGUF ecosystem on Hugging Face.")
    p.add_argument("--top", type=int, default=200,
                   help="number of top-downloaded GGUF repos to sample "
                        "(default: 200)")
    p.add_argument("--per-org", type=int, default=2,
                   help="cap on repos sampled per publisher/org, so the "
                        "download ranking isn't dominated by a handful of "
                        "publishers (default: 2)")
    p.add_argument("--out", metavar="PATH",
                   help="write the raw per-repo JSON results to PATH")
    p.add_argument("--markdown", metavar="PATH",
                   help="write the markdown report to PATH (it is also "
                        "always printed to stdout)")
    p.add_argument("--save-templates", metavar="DIR",
                   help="also write every fetched chat template (and its upstream, "
                        "when resolved) to DIR as <org>__<repo>.jinja with a .json "
                        "sidecar recording repo, revision, licence and tokens")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # argv[0] == "survey" normally means the survey subcommand -- but a
    # local file or repo id that happens to be named exactly "survey" must
    # still lint as a normal target, the same way is_repo_id() always
    # prefers an on-disk path over guessing at a name's shape. Checking
    # existence here, before dispatch, keeps that one rule consistent in
    # both places instead of only in resolve().
    if argv and argv[0] == "survey" and not os.path.exists("survey"):
        return _survey_main(argv[1:])
    return _lint_main(argv)


def _lint_main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.require_upstream and not args.compare_upstream:
        # --require-upstream asks the tool to fail when a requested
        # comparison couldn't be resolved. With no --compare-upstream there
        # is no comparison to have requested in the first place, so this
        # combination can never mean anything the user intended -- reject it
        # up front rather than let it silently fail on coverage.upstream ==
        # "not_requested" (declining a comparison is not the same as failing
        # one).
        print("ggufdoctor: --require-upstream requires --compare-upstream",
              file=sys.stderr)
        return 2

    if args.runtime:
        from ggufdoctor.sources import is_repo_id
        if is_repo_id(args.target):
            # `ollama create` needs a file it can point a Modelfile FROM at,
            # and ggufdoctor will not download one to hand it: a repo id here
            # is a request the tool cannot honour, not a run it should start
            # and abandon halfway through.
            print("ggufdoctor: --runtime needs a local .gguf file", file=sys.stderr)
            return 2

    try:
        from ggufdoctor.sources import resolve
        model, upstream, coverage = resolve(args.target, args.compare_upstream)
        corpus = load_corpus(args.fixtures)
        fixtures = corpus.fixtures

        from ggufdoctor.checks.cross_engine import X_IDS, run_cross_engine_checks
        from ggufdoctor.engines.registry import select_engines

        requested = ([n.strip() for n in args.engines.split(",") if n.strip()]
                     if args.engines else None)
        selection = select_engines(requested)   # ValueError -> "ggufdoctor: ..." exit 2 below
        engines = selection.engines
        coverage.engines_unavailable = dict(selection.unavailable)
        ctx = CheckContext(model=model, engines=engines, fixtures=fixtures,
                           upstream_template=upstream,
                           upstream_meta={"coverage": coverage.upstream},
                           corpus_version=corpus.version, custom_corpus=corpus.custom)
        findings = run_sanity_checks(ctx)
        if len(engines) >= 2:
            findings += run_cross_engine_checks(ctx)
            coverage.families_run.insert(coverage.families_run.index("S") + 1, "X")
            coverage.engines_agreed_fixtures = ctx.stats.get("engines_agreed_fixtures")
        elif selection.unavailable:
            # X was not declined -- it could not run. That is a coverage gap.
            ctx.checks_not_evaluated.extend(X_IDS)

        from ggufdoctor.checks.ollama_registry import run_ollama_checks
        findings += run_ollama_checks(ctx)
        ollama_stats = ctx.stats.get("ollama")
        coverage.ollama = ollama_stats
        if ollama_stats and ollama_stats["not_evaluated"] is None:
            anchor = "X" if "X" in coverage.families_run else "S"
            coverage.families_run.insert(coverage.families_run.index(anchor) + 1, "O")

        if upstream or coverage.upstream == "not_found":
            findings += run_reference_checks(ctx)

        if args.runtime:
            # Opt-in only, and last: it is the one family that touches a
            # process and a socket the operator owns, and an OllamaRuntimeError
            # from it takes the same route as any other operator-fixable
            # condition -- "ggufdoctor: ..." and exit 2, below.
            from ggufdoctor.runtime_ollama import OllamaRuntime, run_runtime_checks
            findings += run_runtime_checks(ctx, OllamaRuntime([args.runtime]), args.target)
            if (ctx.stats.get("runtime") or {}).get("not_evaluated") is None:
                coverage.families_run.append("RT")

        rules = load_ignores(args.ignore_file)
        findings, suppressed = apply_ignores(findings, rules)

        # The checks above may have recorded, on ctx, ids of checks that
        # could not evaluate at all (see models.CheckContext.checks_not_
        # evaluated -- e.g. S005/S006 skipping when bos/eos token metadata
        # is missing or out of range). `coverage` was built by resolve()
        # before any check ran, so it knows nothing about that yet. Both
        # report renderers key off `coverage.checks_not_evaluated`, not
        # ctx's copy, so without this merge a model the tool could not fully
        # check would be reported as clean.
        coverage.checks_not_evaluated = list(ctx.checks_not_evaluated)

        report = render_human(model, findings, suppressed, coverage, engines)

        # All I/O that can fail on an expected, operator-fixable condition
        # (an unwritable --json path, same as an unreadable --target or a
        # malformed --ignore-file above) must stay inside this try block:
        # the contract is a one-line "ggufdoctor: ..." message and exit 2,
        # never a stack trace.
        if args.json_path:
            payload = build_json(model, findings, suppressed, coverage, engines,
                                 corpus_version=corpus.version)
            with open(args.json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=1)
    except Exception as e:  # unreadable input, network failure, bad ignore
                            # file, unwritable --json path
        print(f"ggufdoctor: {e}", file=sys.stderr)
        return 2

    print(report)

    if args.require_upstream and coverage.upstream != "ok":
        return 1
    return exit_code(findings, args.fail_on)


def _survey_main(argv: list[str]) -> int:
    import json as _json

    from ggufdoctor.hf import HfClient
    from ggufdoctor.survey import survey, to_markdown

    args = _build_survey_parser().parse_args(argv)

    try:
        result = survey(HfClient(), top=args.top, per_org=args.per_org,
                        save_templates=args.save_templates)
    except Exception as e:
        print(f"ggufdoctor survey: {e}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            _json.dump(result, f, indent=1)
    md = to_markdown(result)
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(md)
    print(md)
    return 0
