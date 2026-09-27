# Rubric: is this reproduction package ready to post?

## Checks

| Check | Evidence | Pass condition | Weight |
|---|---|---|---|
| environment_recorded | The candidate repro report's environment section and header block compared against the issue description and thread highlights | The report explicitly names the environment details (operating system, tool/package version, and runtime/driver specifications) AND explicitly acknowledges any version or platform deviation from the issue description (e.g., if the issue is reported on latest/main or a specific version like 2.3.3, testing an older version like 1.5.3 without explicitly noting the version delta fails this check) | required |
| followable_and_public_steps | The candidate repro report's reproduction steps, configuration files, and repository setup instructions | The steps are exact, complete, sequentially followable by a stranger starting from a fresh setup, and rely on shared/public configurations rather than unshared private monorepos or private configs | required |
| exact_trigger_syntax | The reproduction commands, CLI arguments, and input syntax in candidate repro report compared directly against the issue context description | The commands and inputs match the specific trigger syntax, CLI options, and arguments described in the issue (or an explicit control run), without altering arguments/syntax to cause unrelated compilation, unbound variable, or CLI validation errors | required |
| matching_artifacts_shown | Terminal outputs, logs, and stack traces in candidate repro report compared directly against expected vs. actual outcomes described in the issue | The report contains terminal output/artifacts that directly demonstrate the specific failing behavior, crash, or panic reported in the issue (or output from a systematic attempt for an honest cannot-reproduce report). Non-bug artifacts such as graceful validation exits, normal session banners, or active escape sequences are not presented as confirming the reported crash | required |
| honest_and_evidenced_claims | Narrative claims in candidate claim comment and repro report evaluated against the attached artifacts | All claims of reproduction, non-reproduction, or root cause diagnosis are strictly supported by shown artifacts, avoiding unbacked root-cause assertions, pure "+1 / me too" claims without artifacts, or false confirmation claims | required |
| specific_modest_claim_comment | Candidate claim comment text evaluated against the issue topic and repo context | The claim comment is human-voiced and specific to the issue's findings or reproduction intent, avoiding generic assign-me boilerplate, generic 2-day fix guarantees, or pure "+1" comments | required |
| repo_ai_disclosure | Repository generative AI policy in repo-facts block and candidate claim comment or repro report text | If the repository's stated policy in repo-facts requires disclosure when generative AI tools are used (e.g. ghostty or p5.js AI disclosure policies), the candidate comments explicitly disclose AI tool assistance | required |

## Verdict rule

Accept the reproduction package if every required check receives a `pass` grade. If any required check receives a `fail` or `unclear` grade, reject the reproduction package. Preferred checks (if any) never change the verdict.
