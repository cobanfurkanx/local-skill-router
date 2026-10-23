# Pilot evidence, not a performance guarantee

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
