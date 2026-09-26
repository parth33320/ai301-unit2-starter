# Evidence guide: where proof lives in a reproduction package

This guide maps every proof family to its exact location in a package (or on GitHub in live mode) and defines the observable criteria for sufficient proof.

## Environment

- **Where it lives**:
  - *Eval mode*: The candidate repro report (under environment/system specifications or header blocks) and candidate claim comment in the package bundle.
  - *Live mode*: The student's draft repro report, draft claim comment, or the issue thread details.
- **What good looks like**:
  - The report explicitly records the operating system, package/tool version, and relevant runtime/driver/environment details.
  - If the tested environment or version differs from the version in the issue report, the version delta is explicitly acknowledged and noted.
  - The setup uses public, reproducible configurations rather than unshared private monorepos or unshared private configs that a stranger cannot re-run.

## Steps

- **Where it lives**:
  - *Eval mode*: The candidate repro report under reproduction steps, shell commands, scripts, or config file blocks in the package bundle.
  - *Live mode*: The draft repro comment's reproduction steps section or attached reproduction script.
- **What good looks like**:
  - Steps are complete, exact, and followable sequentially by a stranger starting from a fresh environment.
  - The commands, CLI arguments, configuration options, and input syntax directly target the trigger described in the issue (or an exact control run), without altering arguments/syntax to trigger unrelated errors (such as argument validation errors or unbound variable syntax errors).

## Behavior shown

- **Where it lives**:
  - *Eval mode*: Output excerpts, terminal logs, stack traces, or artifacts in the candidate repro report, evaluated directly against the issue context description and expected vs. actual output.
  - *Live mode*: Terminal logs, command outputs, or visual artifacts attached to the draft report read against the target issue.
- **What good looks like**:
  - Artifacts directly show the actual failing output, crash, stack trace, or unexpected behavior reported in the issue (or show clear output of an attempt when reporting a cannot-reproduce result).
  - Graceful validation errors (e.g. exit 1 argument error) are not presented as confirming crashes or panics (e.g. exit 101 capacity overflow crash).
  - Output showing active, non-crashed states (e.g. garbled escape sequences with terminal alive) is not presented as a crash.

## Honesty

- **Where it lives**:
  - *Eval mode*: The candidate repro report's narrative/summary and candidate claim comment compared against the actual artifacts present in the package bundle.
  - *Live mode*: Narrative claims in draft comments compared against the executed test results and log outputs.
- **What good looks like**:
  - All claims of reproduction or non-reproduction strictly match the shown evidence.
  - Pure "+1 / me too" claims without supporting artifacts, unbacked root cause assertions ("I verified this race condition" without log traces), or guaranteed fix promises are absent.
  - An attempt that fails to trigger the bug honestly reports "cannot reproduce", includes the attempt artifacts/control runs, and identifies plausible setup/environment differences.

## Comms

- **Where it lives**:
  - *Eval mode*: Candidate claim comment, candidate repro report, and the `repo-facts` block in the package bundle (which contains the repository's contribution policy and generative AI rules).
  - *Live mode*: Draft claim comment, draft repro report, and the target repository's `CONTRIBUTING.md` / AI policy documentation on GitHub.
- **What good looks like**:
  - The claim comment is human-voiced, specific, and modest, stating intent to investigate or share findings rather than using generic assign-me boilerplate or promising guaranteed fixes.
  - If the repository's stated policy requires disclosure when generative AI tools are used (e.g., policies explicitly requiring disclosure in `ghostty-org/ghostty` or `processing/p5.js`), the package explicitly includes an AI assistance disclosure statement.
