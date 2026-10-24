# Pilot evidence, not a performance guarantee

## Codex capability-loop repeat — 2026-10-24

One randomized pair tested runtime commit `e79428b033d632dbdf9e4eb06aff41a09e6105b4` with native Codex Desktop CLI `0.163.0-alpha.11.2`, model `gpt-6.1-sol`, medium reasoning. The task was RelayDesk: a Python standard-library/SQLite multi-tenant webhook laboratory with HMAC authentication, idempotency, cursor pagination, atomic claims across two processes, lease fencing, retry/dead-letter handling, a Turkish responsive UI, tests and documentation.

Both arms had identical snapshots of ten native skills and independent homes/workspaces. Both were permitted bounded public skill discovery and one reviewed installation into their isolated test home. Only the treatment added the router adapter/workflow. Order was randomized before inference: router on, then off. Each run had a 20-minute limit; neither timed out. No output was regenerated or manually repaired to obtain a better comparison.

| Observed field | Router off | Router on |
|---|---:|---:|
| Independent fixed HTTP checks | 26/26 | 25/26 |
| Native input (includes cached input) | 1,103,289 | 1,371,664 |
| Cached input | 1,059,584 | 1,327,872 |
| Uncached input | 43,705 | 43,792 |
| Output (includes reasoning) | 32,591 | 32,560 |
| Reasoning subset | 6,059 | 3,726 |
| Input + output | 1,135,880 | 1,404,224 |
| Wall seconds | 735.235 | 719.703 |
| Observed command/file-change operations | 21 | 36 |
| Nonzero command exits, including RED tests/recovered failures | 5 | 7 |

The router-on artifact rounded retry timing to integer seconds. A separate post-check probe observed a retry claim after **1.265 seconds**, below the required two seconds; the off artifact retried after **2.031 seconds**. The fixed test score was not changed by this probe. Later assertions in the failed retry/dead-letter test group did not execute for the on artifact. Other authentication, isolation, concurrency and persistence checks passed in both arms.

The treatment read the router workflow and invoked local retrieval. Both arms read frontend and security skills. Neither used the remote helper or installed a new skill, and no skills.sh/GitHub discovery command was observed. Thus this run does not demonstrate the remote-discovery branch or its quality impact. Native agents attempted browser checks but reported Chrome profile access failures. After generation, the evaluator independently exercised tenant switching, signed event creation, claim and successful completion in both UIs; both worked. Both were also inspected at a verified 390px viewport without document-level horizontal overflow. These checks are not a full accessibility or visual-quality audit.

**This pair did not demonstrate an output-quality advantage from routing.** The accumulated input+output count was about 23.6% higher with routing, but almost all of that difference was cached input; uncached input and output were nearly equal. Do not interpret accumulated tokens as unique context size, money or subscription quota. Cache/reasoning fields are subsets, not additions. The valid-pair subtotal is **2,540,104 tokens**; coordinating-chat usage is unknown and excluded. All failed commands remain in native usage/time.

The task's functional contract and 26 checks were unchanged from the earlier local-only RelayDesk pair (25/26 in both arms). This repeat changed discovery permissions equally in both arms, so cross-run changes cannot be attributed solely to the new router workflow. One stochastic pair, sequential shared-prefix caching, private skill snapshots and incomplete browser verification during generation prevent general, causal or production-readiness claims. Raw sessions, credentials and private libraries are not published. This is an exploratory report, not a public reproducible benchmark suite.

## Earlier ledger pilot

An exploratory pilot ran on 2026-10-22, using the local predecessor of this portable package. It did **not** benchmark this packaged release or compare competing router repositories.

Task: fix a synthetic Python ledger aggregator, including strict input validation, Decimal totals, normalized duplicate identities, conflict rejection, deterministic account ordering and unittest coverage. Each condition started in a separate workspace and session with the same task and initial code.

| Native client / requested model | Router off → on, initial checks | Reported native total off → on | Wall seconds off → on |
|---|---|---:|---:|
| Antigravity / `gemini-3.8-flash-medium` | 25/25 → 25/25 | 101,520 → 84,114 | 216.751 → 101.615 |
| OpenCode / `opencode/glm-5.3-flash-free` | 25/25 → 25/25 | 494,909 → 612,983 | 67.122 → 91.559 |

Both routing-on runs invoked the router and read a debugging and test-driven-development skill. Neither routing-off run invoked the router or read skill files. One recovered wrong-path read in the valid OpenCode run remained in its measured overhead.

**Every candidate failed a supplemental test involving more than 28 digits of Decimal precision.** That check was added after the initial pilot and is reported separately. Passing the initial suite did not establish complete correctness. Code aesthetics and visual UI quality were not assessed.

## Token accounting

| Native field | Antigravity off | Antigravity on | OpenCode off | OpenCode on |
|---|---:|---:|---:|---:|
| Input | 83,339 | 79,754 | 69,069 | 79,720 |
| Output | 18,181 | 4,360 | 2,504 | 2,503 |
| Thinking / reasoning | 14,109 | 0 | 104 | 904 |
| Cache read | 279,711 | 253,058 | 423,232 | 529,856 |

Antigravity's observed total equals input + output, with cache reported separately. Its thinking counter was not added again. OpenCode's observed step totals include input + output + reasoning + cache read; its step counters were summed. Do not combine these clients into one savings percentage or infer account billing from the totals. The zero thinking count in one condition needs further investigation before causal interpretation.

Two initial OpenCode calls were invalid because a Windows `.cmd` shim truncated the multiline task; one also encountered a skill read permission denial. Those calls consumed a reported 240,545 native tokens and 42.224 total wall seconds. They were excluded from the benefit comparison but remain experiment setup overhead. The corrected pair used the native executable and process-scoped skill directory access. The coordinating agent's own usage was not measured.

## Limits

- One task and one pair per client. No significance or causal claim is justified.
- Order was off→on in Antigravity and on→off in OpenCode. That does not remove cache/order effects within either model. Requested models were fixed; backend reasoning variation was not controlled.
- Both conditions inherited the same native catalogue. This does not isolate catalogue suppression or the router's startup metadata overhead.
- The on condition used a supplied generic domain query. End-to-end autonomous query formation was not separately tested.
- Functional checks were independent of agent-written tests. Quantity of generated tests and code lines was not treated as a quality score.
- Private native sessions and local libraries are not redistributed, so these are an anonymized exploratory report, not a public reproducible benchmark dataset.
- No background experiments, native client launches or paid calls are included in this package.

For stronger evidence, define the checks before generation, use multiple held-out tasks and repeated randomized/counterbalanced pairs within each model, verify routing compliance, separate cache/reasoning accounting, and report failed attempts rather than selecting only favorable runs.
