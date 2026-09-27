#!/usr/bin/env python3
"""Eval harness: grade every reproduction-package bundle with the
repro-check skill and a chosen rubric plus evidence guide, then score
agreement against the gold labels.

Uses Google Gemini API instead of Claude CLI.
"""

import argparse
import concurrent.futures
import hashlib
import json
import logging
import os
import re
import sys
import threading
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Suppress SDK deprecation and warning logs
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)

from google import genai

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-3.5-flash-lite"
JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

PROMPT_TEMPLATE = """\
{skill}

----------------------------------------------------------------------
# Rubric (rubric.md)

{rubric}

----------------------------------------------------------------------
# Evidence guide (references/evidence-guide.md)

{evidence}

----------------------------------------------------------------------
# Eval package: {item_id}

{bundle}

----------------------------------------------------------------------
Run the repro-check skill above in EVAL MODE on this package bundle.
The bundle text is your only evidence; do not fetch or read anything
else, and ignore scope.md and voice-guide.md entirely (eval mode).
Grade every check in the rubric using the evidence guide's map, apply
the rubric's verdict rule, and end your reply with the fenced JSON
block the skill's output format requires, using "{item_id}" as the
item id.
"""

RATE_LIMIT_LOCK = threading.Lock()
LAST_REQUEST_TIME = 0.0


def rate_limited_call(client: genai.Client, prompt: str, model_name: str):
    global LAST_REQUEST_TIME
    with RATE_LIMIT_LOCK:
        now = time.time()
        elapsed = now - LAST_REQUEST_TIME
        if elapsed < 0.5:
            time.sleep(0.5 - elapsed)
        LAST_REQUEST_TIME = time.time()

    return client.models.generate_content(
        model=model_name,
        contents=prompt,
    )


def grade_one(item_id: str, bundle_path: Path, skill: str, rubric: str,
              evidence: str, timeout: int, api_key: str, model_name: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        skill=skill, rubric=rubric, evidence=evidence, item_id=item_id,
        bundle=bundle_path.read_text(encoding="utf-8"))

    client = genai.Client(api_key=api_key)
    last_err = "no attempt"
    active_model = model_name

    for attempt in range(2):                     # attempts for valid JSON output
        output_text = ""
        for api_retry in range(5):
            try:
                response = rate_limited_call(client, prompt, active_model)
                output_text = response.text or ""
                if output_text:
                    break
            except Exception as e:
                err_str = str(e)
                last_err = f"gemini api error ({active_model}): {err_str}"
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if active_model == DEFAULT_MODEL:
                        active_model = FALLBACK_MODEL
                        time.sleep(1)
                    else:
                        time.sleep(10 + api_retry * 5)
                elif "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep(3 + api_retry * 2)
                else:
                    time.sleep(2)

        if not output_text:
            continue

        blocks = JSON_BLOCK_RE.findall(output_text)
        if not blocks:
            snippet = " ".join(output_text.split())[-160:]
            last_err = f"no fenced JSON block in output from {active_model}" + \
                (f"; model output ended: ...{snippet}" if snippet else "")
            continue
        try:
            data = json.loads(blocks[-1])
        except ValueError as e:
            last_err = f"bad JSON: {e}"
            continue
        verdict = str(data.get("verdict", "")).lower()
        if verdict not in ("accept", "reject"):
            last_err = f"verdict is {verdict!r}, not accept/reject"
            continue
        failed = [c.get("name", "?") for c in data.get("checks", [])
                  if str(c.get("grade", "")).lower() != "pass"]
        return {"id": item_id, "verdict": verdict, "failed_checks": failed,
                "checks": data.get("checks", []), "error": None}
    return {"id": item_id, "verdict": None, "failed_checks": [],
            "checks": [], "error": last_err}


def rubric_has_checks(text: str) -> bool:
    """True if any checks-table row carries a required/preferred weight."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for line in body.splitlines():
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[-1] in ("required", "preferred"):
            return True
    return False


def rubric_has_verdict_rule(text: str) -> bool:
    """True if the rubric carries prose outside comments, headings, and
    the checks table (a filled rubric states its verdict rule as plain
    text below the table)."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return any(line.strip() and not line.lstrip().startswith(("#", "|"))
               for line in body.splitlines())


def guide_has_content(text: str) -> bool:
    """True if the evidence guide carries prose beyond the template's
    headings (the shipped template is family headings plus comments)."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return any(line.strip() and not line.lstrip().startswith("#")
               for line in body.splitlines())


class _Tee:
    """Mirror everything printed to the screen into a buffer as well, so
    --save-run can write the transcript the student saw."""

    def __init__(self, stream):
        self.stream = stream
        self.buf: list[str] = []

    def write(self, s: str) -> int:
        self.buf.append(s)
        return self.stream.write(s)

    def flush(self) -> None:
        self.stream.flush()

    def isatty(self) -> bool:
        return self.stream.isatty()

    def text(self) -> str:
        return "".join(self.buf)


def write_run(path: str, graded: str, files: list, n_items: int,
              transcript: str) -> None:
    """Write the run transcript to a file, UTF-8 on every platform, under a
    provenance header the student did not type: what was graded, on which
    model, and a fingerprint of each file that went into the run."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    head = [f"# eval run written by run_eval.py at {stamp}",
            f"# model: sonnet (pinned)",
            f"# graded: {graded}",
            f"# packages: {n_items} scored"]
    for p in files:
        digest = hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
        head.append(f"#   {Path(p).name}  sha256:{digest}")
    head.append("#")
    Path(path).write_text("\n".join(head) + "\n" + transcript,
                          encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Grade the eval set with a rubric plus evidence "
                    "guide and score agreement.")
    ap.add_argument("--rubric", default=str(HERE.parent / "skill" / "rubric.md"),
                    help="path to the rubric file to grade with")
    ap.add_argument("--evidence", default=str(HERE.parent / "skill" / "references" / "evidence-guide.md"),
                    help="path to the evidence guide to grade with")
    ap.add_argument("--skill", default=str(HERE.parent / "skill"
                                           / "SKILL.md"),
                    help="path to SKILL.md (default: the week's skill)")
    ap.add_argument("--packages", default=str(HERE / "packages"))
    ap.add_argument("--gold", default=str(HERE / "gold-labels.json"))
    ap.add_argument("--include-calibration", action="store_true",
                    help="also grade the 4 worksheet calibration packages "
                         "(never scored)")
    ap.add_argument("--only", default=None, metavar="ID[,ID...]",
                    help="grade only these package ids, comma-separated "
                         "(e.g. --only pkg-07,pkg-12); cheap re-runs "
                         "while revising a rubric")
    ap.add_argument("--limit", type=int, default=0,
                    help="grade only the first N items (smoke runs)")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=420,
                    help="seconds per package per attempt")
    ap.add_argument("--save-run", default=None, metavar="FILE",
                    help="write this run's output to FILE (the run you "
                         "commit); refused on partial runs")
    ap.add_argument("--out", default=None,
                    help="also write full results as JSON to this path")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"gemini model name (default: {DEFAULT_MODEL})")
    a = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("error: GEMINI_API_KEY environment variable is not set", file=sys.stderr)
        return 2

    run_log = None
    if a.save_run:
        run_log = _Tee(sys.stdout)
        sys.stdout = run_log

    rubric_p = Path(a.rubric)
    evidence_p = Path(a.evidence)
    skill_p = Path(a.skill)
    for p, what in ((rubric_p, "rubric"), (evidence_p, "evidence guide"),
                    (skill_p, "skill")):
        if not p.is_file():
            print(f"error: {what} not found at {p}", file=sys.stderr)
            return 2
    rubric = rubric_p.read_text(encoding="utf-8")
    evidence = evidence_p.read_text(encoding="utf-8")
    skill = skill_p.read_text(encoding="utf-8")

    if not rubric_has_checks(rubric):
        print(f"error: {rubric_p} has no filled-in checks. The shipped "
              "template is empty on purpose; the skill refuses to grade "
              "without a rubric. Write your checks and verdict rule "
              "first, then point --rubric at your filled copy.",
              file=sys.stderr)
        return 2
    if not rubric_has_verdict_rule(rubric):
        print(f"error: {rubric_p} has checks but no verdict rule. State "
              "below the checks table how the grades combine into accept "
              "or reject, including how unclear is treated; the template's "
              "Verdict rule section shows the shape. Without one, the "
              "grader invents its own combination rule and the run is "
              "wasted money.", file=sys.stderr)
        return 2
    if not guide_has_content(evidence):
        print(f"error: {evidence_p} has no filled-in content. The shipped "
              "template is family headings only; the skill needs your map "
              "of where proof lives. Fill it, then point --evidence at "
              "your filled copy.", file=sys.stderr)
        return 2

    gold = json.loads(Path(a.gold).read_text(encoding="utf-8"))
    items = [it for it in gold["items"]
             if a.include_calibration or not it.get("calibration")]
    if a.only:
        wanted = [s.strip() for s in a.only.split(",") if s.strip()]
        known = {it["id"] for it in items}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            print(f"error: --only ids not in the eval set: "
                  f"{', '.join(unknown)} (calibration packages need "
                  "--include-calibration)", file=sys.stderr)
            return 2
        items = [it for it in items if it["id"] in set(wanted)]
    if a.limit:
        items = items[:a.limit]
    if not items:
        print("error: no items to grade", file=sys.stderr)
        return 2

    packages_dir = Path(a.packages)
    missing = [it["id"] for it in items
               if not (packages_dir / f"{it['id']}.md").is_file()]
    if missing:
        print(f"error: bundle files missing: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    print(f"grading {len(items)} package(s) with {rubric_p.name} + "
          f"{evidence_p.name}, model sonnet, {a.workers} worker(s)...",
          flush=True)
    results: dict[str, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(a.workers) as pool:
        futs = {pool.submit(grade_one, it["id"],
                            packages_dir / f"{it['id']}.md",
                            skill, rubric, evidence, a.timeout, api_key, a.model): it["id"]
                for it in items}
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results[r["id"]] = r
            state = r["verdict"] or f"ERROR ({r['error']})"
            print(f"  {r['id']}: {state}", flush=True)

    errors = 0
    scored_total = scored_agree = 0
    cats: dict[str, list[int]] = {}     # category -> [matches, scored items]
    rows = []
    for it in items:
        r = results[it["id"]]
        gold_v = it["verdict"]
        if r["error"]:
            errors += 1
            if not it.get("calibration"):
                cats.setdefault(it.get("category", "?"), [0, 0])[1] += 1
            rows.append((it["id"], gold_v, "ERROR", "", r["error"]))
            continue
        is_scored = not it.get("calibration")
        match = r["verdict"] == gold_v
        if is_scored:
            scored_total += 1
            scored_agree += int(match)
            c = cats.setdefault(it.get("category", "?"), [0, 0])
            c[1] += 1
            c[0] += int(match)
        note = "" if match else \
            ("failed: " + ", ".join(r["failed_checks"])
             if r["verdict"] == "reject" else "graded accept")
        rows.append((it["id"], gold_v, r["verdict"],
                     "yes" if match else "NO", note))

    wid = max(len(r[0]) for r in rows)
    print(f"\n{'item'.ljust(wid)}  gold    verdict  agree  note")
    for item_id, g, v, m, note in rows:
        print(f"{item_id.ljust(wid)}  {g:7} {v:8} {m:6} {note}")

    bar = gold.get("pass_bar")
    full_scored = sum(1 for it in gold["items"] if not it.get("calibration"))
    partial = scored_total != full_scored
    if partial:
        bar = None                      # partial run; the bar reads 20 items
    if cats:
        print("\ncategories: " + "  ".join(
            f"{k} {m}/{t}" for k, (m, t) in sorted(cats.items())))
        print(f"agreement: {scored_agree}/{scored_total} scored items",
              end="")
    else:
        print(f"\nagreement: {scored_agree}/{scored_total} scored items",
              end="")
    if bar is not None:
        floor_missing = sorted(k for k, (m, _) in cats.items() if m == 0)
        # The bar is 18/20 AND the category floor: at least one matching
        # verdict in every composition category (grading tab).
        if floor_missing:
            print(f"  (bar: {bar}/{scored_total}: below the bar; category "
                  f"floor unmet: no match in {', '.join(floor_missing)})")
        elif scored_agree >= bar:
            print(f"  (bar: {bar}/{scored_total}: PASS)")
        else:
            print(f"  (bar: {bar}/{scored_total}: below the bar)")
    else:
        print()
        if partial and scored_total:
            print("partial run: the bar and the category floor are decided "
                  "only by a full run. A loosened check can flip a package "
                  "that agreed before; add a canary from each "
                  "single-package category your change touches to --only "
                  "before the confirming full run.")
    if errors:
        print(f"{errors} item(s) errored; fix and re-run.", file=sys.stderr)

    if run_log is not None:
        sys.stdout = run_log.stream
        if scored_total != full_scored:
            print(f"partial run: NOT written to {a.save_run}. Partial runs "
                  "are for finding problems; the run you commit comes from "
                  "one full run of your finished tool.")
        elif errors:
            print(f"{errors} item(s) errored: NOT written to {a.save_run}. "
                  "Fix and re-run.")
        else:
            write_run(a.save_run, str(rubric_p.parent), [rubric_p, evidence_p, skill_p], scored_total,
                      run_log.text())
            print(f"run written to {a.save_run}")

    if a.out:
        Path(a.out).write_text(json.dumps({
            "rubric": str(rubric_p), "evidence": str(evidence_p),
            "model": a.model,
            "agreement": [scored_agree, scored_total],
            "results": [dict(results[it["id"]], gold=it["verdict"],
                             calibration=bool(it.get("calibration")))
                        for it in items]}, indent=2),
            encoding="utf-8")
        print(f"full results written to {a.out}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
