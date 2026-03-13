# Pitfalls Research

**Domain:** Deterministic workflow engine / state machine with rewind-replay, retry counters, FBR gauntlet, and triage sub-pipeline
**Researched:** 2026-03-13
**Confidence:** HIGH (domain-specific analysis grounded in transition table and architecture docs)

## Critical Pitfalls

### Pitfall 1: Counter Scope Confusion — Which Counter Gets Reset on Rewind?

**What goes wrong:**
The engine has at least four distinct counter families: per-node conditional counters (3 max before auto-Fail), per-node retry counters, FBR gauntlet depth counter, and triage retry counter. When a Fail rewinds to a write node and replays forward, the question is: which counters reset and which persist? Get this wrong and you either (a) allow infinite loops because counters reset that shouldn't, or (b) unfairly punish jobs because counters persist that shouldn't.

Example: ReviewBdd gives Conditional twice, then Fail. Job rewinds to WriteBddTestArch and replays forward. When it reaches ReviewBdd again, does the conditional counter start at 0 or 2? If 2, the agent gets one shot before auto-Fail — that's probably wrong since this is a full rewrite, not a targeted fix.

**Why it happens:**
Developers treat "retry count" as a single concept. In reality, this system has counters scoped to different lifecycle boundaries (per-attempt, per-review-pass, per-gauntlet-run, per-triage-cycle). The transition table says what happens but doesn't fully specify counter reset semantics for every rewind path.

**How to avoid:**
Define a `CounterPolicy` that explicitly declares, for every counter type:
- Reset trigger: what event zeros this counter
- Scope: what boundary contains it (single review pass, full pipeline pass, gauntlet run, triage cycle)
- Exhaustion action: what happens when max is hit

Write this as a table before writing code. Test it with scenario traces: "job hits Conditional 3x at ReviewBrd, then Fails, rewinds to WriteBrd, gets back to ReviewBrd — what are the counters?"

**Warning signs:**
- Counter reset logic is implicit (buried in transition handlers rather than explicit policy)
- No unit tests that trace a job through rewind-and-replay and assert counter values at each node
- Off-by-one bugs in "4th conditional auto-promotes to Fail" (is it >=3 or >3?)

**Phase to address:**
Phase 1 (core state machine). Counter semantics must be designed before any transitions are coded. This is load-bearing.

---

### Pitfall 2: Rewind-Replay Doesn't Actually Replay — Stale Artifacts Survive

**What goes wrong:**
When a Fail at ReviewFsd rewinds to WriteFsd and the job "replays the full pipeline forward," the engine must invalidate all downstream artifacts. If it doesn't, downstream nodes may consume stale artifacts from the previous pass. Example: the FSD gets rewritten, but BuildJobArtifacts still sees the old FSD cached somewhere, builds against it, and the review passes because the reviewer is checking the new FSD against old artifacts that happen to match.

In v0.1 with stubs this is invisible. In production with real agents reading real files, it's catastrophic — you get silent correctness failures where everything "passes" but the artifacts are inconsistent.

**Why it happens:**
The engine tracks state transitions but not artifact lineage. "Replay forward" means "re-execute nodes in order" but doesn't inherently mean "wipe the slate." Artifact invalidation is a separate concern from state transition.

**How to avoid:**
Model artifact invalidation explicitly. When a rewind occurs:
1. Record which node the rewind targets
2. Mark all artifacts produced by that node and every downstream node as invalid
3. Each node, on entry, asserts its input artifacts are valid (not stale-marked)

For v0.1 stubs: simulate this with a `artifact_version` counter per node. Each execution increments it. Downstream nodes record which version of upstream artifacts they consumed. On rewind, assert version consistency.

**Warning signs:**
- No concept of "artifact version" or "artifact validity" in the job state model
- Rewind logic only updates `current_node` without touching artifact metadata
- Integration tests pass in v0.1 but would silently fail with real artifacts

**Phase to address:**
Phase 1 design, Phase 2 implementation. The v0.1 stub layer should at minimum track a generation counter per node to prove the invalidation logic works, even if no real artifacts exist yet.

---

### Pitfall 3: FBR Gauntlet Creates Combinatorial Explosion of Paths

**What goes wrong:**
The FBR gauntlet has 6 serial gates. Each gate can Approve, Conditional (which routes to response node, then review, then restarts gauntlet from top), or Fail (which rewinds to original write node, replays forward through the entire pipeline, and eventually re-enters the gauntlet). With a depth cap of N, the theoretical path space is enormous. A single FBR_FsdCheck Conditional triggers: WriteFsdResponse -> ReviewFsd -> FBR_BrdCheck -> FBR_BddCheck -> FBR_FsdCheck (6+ transitions). A Fail triggers even more.

The combinatorial explosion makes it nearly impossible to reason about correctness by inspection. You need automated path coverage.

**Why it happens:**
The gauntlet design is correct — a downstream fix genuinely can invalidate an upstream pass. But the "always restart from top" invariant means every failure multiplies the path count. Developers underestimate how many distinct paths exist and write tests for the obvious ones while missing edge cases like "FBR_BddCheck Conditional, fix, restart, then FBR_FsdCheck Fail on the second pass."

**How to avoid:**
1. Build a path enumeration tool early. Given the transition table, enumerate all possible paths through the gauntlet up to depth cap N. Use this to generate test scenarios automatically.
2. Instrument the engine to log the full path trace (sequence of nodes visited). After running N jobs with RNG outcomes, assert that path coverage includes at least the critical edge cases.
3. Keep the depth cap low (2-3). The math on combinatorial paths with depth cap 5+ is ugly.

**Warning signs:**
- Manual test case lists that only cover "happy path" and "one failure" scenarios
- No path trace logging
- FBR depth cap set high "just in case" without understanding the path explosion
- Tests pass but only exercise a tiny fraction of possible gauntlet paths

**Phase to address:**
Phase 1 (design the depth cap), Phase 2 (build path enumeration), Phase 3 (run RNG simulations and measure path coverage).

---

### Pitfall 4: Conditional vs. Fail Routing Ambiguity at FBR Gates

**What goes wrong:**
In-flow reviews and FBR gates both use the three-outcome model (Approve/Conditional/Fail), but the routing is subtly different. For in-flow reviews, Conditional goes to response node and returns to the same reviewer. For FBR gates, Conditional goes to response node, goes through review, then restarts the entire gauntlet from FBR_BrdCheck. The FBR Fail path is even more different — it rewinds to the original write node and replays the entire pipeline forward.

If the engine uses a single generic "handle review outcome" function, the FBR-specific routing gets wrong. Or worse, it gets the Conditional right but the Fail wrong (or vice versa).

**Why it happens:**
DRY instinct. "Review nodes all work the same way" is true for the outcome model but false for the routing. Developers abstract too early and the abstraction leaks.

**How to avoid:**
Make the transition table the source of truth in code, not just in documentation. Each node should declare its own transition map: `{APPROVE: next_node, CONDITIONAL: response_node, FAIL: rewind_target}`. The FBR gates declare `{CONDITIONAL: response_node, ..., restart_target: FBR_BrdCheck}` as an additional field. Don't try to derive routing from node type — declare it explicitly per node.

**Warning signs:**
- A `ReviewNode` base class with overridable routing methods (inheritance = bugs)
- FBR routing logic that relies on string matching node names to decide behavior
- Conditional at FBR gate doesn't restart from FBR_BrdCheck (goes back to just that gate)

**Phase to address:**
Phase 1 (transition table as data structure). This should be a literal dictionary/enum mapping, not procedural logic.

---

### Pitfall 5: Triage Sub-Pipeline State Bleeds Into Main Pipeline State

**What goes wrong:**
The triage sub-pipeline (T1-T7) is conceptually separate from the main pipeline but shares the same job. If triage state (which diagnostic step we're on, what faults were found, triage retry counter) is stored in the same flat namespace as main pipeline state, you get collisions. Worse: when triage routes back to a main pipeline node (e.g., WriteBrd), the triage state needs to be cleaned up. If it isn't, the next time the job enters triage, it sees stale diagnostic results from the previous triage pass.

**Why it happens:**
The job state object starts as a flat dict: `{current_node: "...", retry_counts: {...}, ...}`. Triage fields get bolted on: `{triage_step: "T3", triage_faults: [...], triage_retry: 2}`. Nobody cleans these up when exiting triage.

**How to avoid:**
Model triage as a nested state scope. The job has a `triage_context` that is created on entry to triage and destroyed on exit. Main pipeline state and triage state are structurally separate. When Triage_Route sends the job back to a main pipeline node, the triage context is archived (for logging) and cleared.

```python
@dataclass
class TriageContext:
    step: str
    faults: list[tuple[str, str]]  # (layer, reason)
    retry_count: int
    data_profile: Any
    og_analysis: Any

@dataclass
class JobState:
    current_node: str
    counters: dict[str, int]
    triage: TriageContext | None  # None when not in triage
```

**Warning signs:**
- Triage fields mixed into the main job state dict
- No explicit "enter triage" / "exit triage" transitions
- Triage retry counter doesn't reset when triage routes back to main pipeline and the job eventually re-enters triage

**Phase to address:**
Phase 1 (job state model design). Get the data model right before implementing triage transitions.

---

### Pitfall 6: "Earliest Fault Wins" Triage Routing Is Ambiguous

**What goes wrong:**
T7 routes to the "earliest" fault when multiple triage checks find problems. But what does "earliest" mean? Earliest in the main pipeline order (BRD before FSD before code before proofmark)? Or earliest triage check that found a fault (T3 before T4 before T5 before T6)? In the current design these happen to be the same order, but the implementation might not encode that assumption correctly. If someone reorders the triage checks or adds a new one, "earliest" silently means the wrong thing.

Additionally: T6 (proofmark config) is described as "only meaningful if T3-T5 all came back clean." If T3 finds a fault AND T6 finds a fault, should T6's fault be ignored (since it might be a false positive caused by T3's underlying issue)? The design doc implies yes, but the routing logic might not enforce it.

**Why it happens:**
The routing rule is stated in English ("earliest fault wins") but the ordering is implicit. Developers implement it as "first fault in a list" without encoding the priority order explicitly.

**How to avoid:**
Define fault priority as an explicit ordered enum:
```python
TRIAGE_PRIORITY = ["BRD", "FSD", "CODE", "PROOFMARK"]
```
T7 routing: sort faults by this priority, take the first. Also: if a higher-priority fault exists, discard lower-priority faults (they may be downstream symptoms).

**Warning signs:**
- Faults stored in a dict (unordered) rather than evaluated against a priority list
- T6 fault is acted on even when T3/T4/T5 also found faults
- No test case for "multiple faults, verify correct routing target"

**Phase to address:**
Phase 2 (triage implementation). Design the priority enum in Phase 1.

---

### Pitfall 7: Fail-Rewind Creates Orphaned Response Nodes in History

**What goes wrong:**
A job is at ReviewBrd. It gets Conditional, goes to WriteBrdResponse, comes back to ReviewBrd. Gets Conditional again, goes to WriteBrdResponse again, comes back. Gets Fail, rewinds to WriteBrd. Now the job walks the full happy path forward. When it hits ReviewBrd again, is this a "fresh" review or does the engine think there are prior Conditionals? If the engine tracks "times this review node has been visited" without distinguishing between pipeline passes, the history from the previous pass contaminates the current one.

This is a specific case of Pitfall 1 (counter scope confusion) but applied to node visit history rather than just counters.

**Why it happens:**
The engine tracks per-node state without a concept of "pipeline pass" or "generation." Each rewind starts a new logical generation, but if the state model is flat, old and new generations are indistinguishable.

**How to avoid:**
Introduce a `generation` counter on the job. Each rewind increments it. Counters and visit history are scoped to `(node_name, generation)`. When generation increments, all per-node counters for affected nodes reset to zero.

**Warning signs:**
- Per-node counters stored as `{node_name: count}` without generation scoping
- A rewind to WriteBrd doesn't reset the conditional counter for ReviewBrd
- Test: "Conditional 2x -> Fail -> rewind -> new pass reaches ReviewBrd -> conditional counter should be 0" — if this test doesn't exist, the bug exists

**Phase to address:**
Phase 1 (state model design). The generation concept must be part of the initial job state schema.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Flat dict for job state | Fast to prototype | Counter scope bugs, triage state bleed, no generation tracking | Never — use dataclasses from day 1, cost is trivial |
| Transition logic in if/elif chains | Easy to read initially | Unmaintainable at 27+ nodes, FBR routing buried in conditionals | v0.1 stub phase only, refactor before adding real agents |
| Hardcoded node order | No need for graph traversal | Can't add nodes or reorder without rewriting routing logic | Never — use a declared transition table data structure |
| Single "handle_review" function for all review types | DRY | FBR routing bugs (Pitfall 4) | Never — declare per-node transitions explicitly |
| Counters as bare ints on job state | Simple | No reset semantics, no generation scoping (Pitfalls 1, 7) | Never — wrap in a Counter class with scope/reset policy |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded FBR depth cap | Jobs loop through gauntlet dozens of times | Set depth cap to 2-3, analyze path explosion before increasing | Immediately if depth cap > 4 — exponential path space |
| Full pipeline replay on every Fail | Single Fail at late node (ReviewUnitTests) triggers replay of 15+ nodes | This is by design, but monitor replay depth. Add circuit breaker: if total node executions for a job exceed threshold, DEAD_LETTER | At scale with 105 jobs, pathological cases could dominate runtime |
| Triage re-executing proofmark repeatedly | Triage finds fault, fixes, re-runs proofmark, fails again, re-triages | Triage retry cap must be low (2-3). Each proofmark execution is expensive | When proofmark involves real data comparison across effective dates |
| Linear scan of 105 jobs checking state | O(n) job polling per engine tick | Use priority queue or state-indexed lookup | Not in v0.1, but design for it now |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Postgres task queue (future) | Storing full job state in the queue row | Queue holds task ID + minimal routing info. Job state lives in a separate table. Queue is claimed-and-released, state is read-and-updated |
| Claude CLI agents (future) | Parsing agent output as trusted | Validate JSON schema of agent responses. Agents can return malformed output. Treat agent output as untrusted input |
| Proofmark execution (future) | Assuming proofmark is deterministic | Proofmark compares data outputs — if the underlying ETL has non-deterministic elements (timestamps, floating point), proofmark may flap. Triage must distinguish "genuine fault" from "noise" |
| File system artifacts (future) | Reading/writing artifacts without locking | In concurrent mode, two agents could write to the same artifact path. Use job-scoped directories with atomic writes |

## "Looks Done But Isn't" Checklist

- [ ] **Rewind logic:** Rewinds to correct write node but doesn't reset downstream counters — verify counter state after rewind with a trace test
- [ ] **FBR Conditional:** Routes to response node and reviewer, but doesn't restart gauntlet from FBR_BrdCheck — verify the full Conditional path, not just the first hop
- [ ] **4th Conditional auto-Fail:** Boundary condition — verify it triggers on exactly the 4th (not 3rd or 5th), and that the resulting Fail follows Fail routing (not Conditional routing)
- [ ] **Triage exit:** Triage routes back to main pipeline node, but triage context (faults, diagnostic artifacts, retry counter) isn't cleaned up — verify triage state is None after exit
- [ ] **DEAD_LETTER:** Node exhausts retries and enters DEAD_LETTER, but the job's `current_node` still points to the failed node — verify DEAD_LETTER is a terminal state that prevents further transitions
- [ ] **FBR depth cap:** Counter increments on gauntlet restart but not on individual gate failures within a single pass — verify the cap counts complete gauntlet restarts, not individual gate visits
- [ ] **Response node routing:** WriteBrdResponse routes back to ReviewBrd (not to the next node in the happy path) — verify response nodes always loop back to their reviewer
- [ ] **Triage routing targets:** T7 routes to main pipeline write nodes (WriteBrd, WriteFsd, etc.), not to review nodes or response nodes — verify the rewind targets match the transition table exactly

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Counter scope confusion (Pitfall 1) | MEDIUM | Add generation tracking to job state, write migration for in-flight jobs, re-run affected jobs |
| Stale artifacts survive rewind (Pitfall 2) | HIGH | Retrofit artifact versioning, audit all completed jobs for consistency, re-run suspect jobs |
| FBR path explosion (Pitfall 3) | LOW | Lower depth cap, add circuit breaker. No data corruption, just wasted compute |
| FBR routing wrong (Pitfall 4) | MEDIUM | Fix transition table, re-run affected jobs. Corruption depends on how far wrong routing went |
| Triage state bleed (Pitfall 5) | MEDIUM | Refactor job state model, clear triage context on affected jobs, re-run from last known good state |
| Triage routing ambiguity (Pitfall 6) | LOW | Fix priority ordering, re-triage affected jobs. Usually caught in testing |
| Orphaned counters across generations (Pitfall 7) | MEDIUM | Add generation scoping, reset counters for in-flight jobs at current generation |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Counter scope confusion | Phase 1: State model design | Unit test: trace job through Conditional -> Fail -> rewind -> re-review, assert counter values |
| Stale artifact survival | Phase 1: Design, Phase 2: Implement | Unit test: rewind at node N, assert all nodes > N have artifact_version incremented |
| FBR path explosion | Phase 1: Set depth cap, Phase 2: Path enumeration | Automated: enumerate paths up to depth cap, report count. Manual: review for sanity |
| FBR routing ambiguity | Phase 1: Transition table as data | Integration test: FBR Conditional and Fail at each gate, verify full routing path |
| Triage state bleed | Phase 1: Job state model | Unit test: enter triage, route back to main pipeline, re-enter triage, assert clean context |
| Triage routing ambiguity | Phase 1: Priority enum, Phase 2: T7 logic | Unit test: multiple faults, verify routing to earliest. Edge case: T6 fault with T3 fault |
| Orphaned counters | Phase 1: Generation concept | Unit test: two full passes through same review node, verify counter independence |

## Sources

- Project transition table: `/workspace/AtcStrategy/POC6/BDsNotes/state-machine-transitions.md`
- Project architecture: `/workspace/AtcStrategy/POC6/BDsNotes/poc6-architecture.md`
- [Temporal retry policies and failure handling](https://temporal.io/blog/failure-handling-in-practice) — retry semantics, activity vs workflow retry distinction
- [LlamaIndex retry counter reset bug](https://github.com/run-llama/llama_index/issues/20403) — counter reset to 0 on retry causing infinite loops
- [Genesys workflow counter types](https://help.genesys.com/latitude/liquid/mergedProjects/WorkFlow/desktop/check_counter.htm) — multiple counter scopes (local, workflow, account) as source of confusion
- [AWS Step Functions redrive](https://aws.amazon.com/blogs/compute/introducing-aws-step-functions-redrive-a-new-way-to-restart-workflows/) — rewind/redrive semantics, only resume from failed state
- [Temporal replay determinism requirements](https://community.temporal.io/t/understanding-how-workflow-replay-is-working/11327) — replay must not re-execute side effects
- [State machines as bug prevention](https://blog.scottlogic.com/2020/12/08/finite-state-machines.html) — invalid state bugs from implicit state machines
- [Argo Workflows retries](https://argo-workflows.readthedocs.io/en/latest/retries/) — retry policy configuration patterns

---
*Pitfalls research for: POC6 Deterministic Workflow Engine*
*Researched: 2026-03-13*
