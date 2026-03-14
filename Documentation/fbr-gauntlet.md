# FBR Gauntlet

Source: `src/workflow_engine/transitions.py` (`FBR_ROUTING`), `src/workflow_engine/step_handler.py`

## What FBR Is

FBR (Final Build Review) is a 7-gate gauntlet that runs after Publish (node 18). It re-verifies every document and artifact produced during the RE workflow before the job proceeds to validation.

The 6 main FBR gates (nodes 19-24) each reuse the same reviewer blueprint as the corresponding in-flow review, but at this point all artifacts exist and can be checked for cross-document consistency.

The 7th gate, FBR_EvidenceAudit (node 28), is the terminal gate in the Validate stage.

## The 7 Gates

| Gate | Checks | Rewind Target |
|---|---|---|
| FBR_BrdCheck | BRD consistency | WriteBrd |
| FBR_BddCheck | BDD consistency | WriteBddTestArch |
| FBR_FsdCheck | FSD consistency | WriteFsd |
| FBR_ArtifactCheck | Artifact consistency | BuildJobArtifacts |
| FBR_ProofmarkCheck | Proofmark config | BuildProofmarkConfig |
| FBR_UnitTestCheck | Unit test coverage | BuildUnitTests |
| FBR_EvidenceAudit | Traceability links | (none -- terminal) |

## Outcome Routing

Each of the 6 main FBR gates (not EvidenceAudit) can return three outcomes:

### APPROVE
Advances to the next FBR gate in happy-path order.

### CONDITIONAL
1. `conditional_counts[gate]` is incremented.
2. `fbr_return_pending` is set to `true`.
3. Job routes to the same response node used by in-flow review (e.g., FBR_BrdCheck -> WriteBrdResponse).
4. Response node does the revision, returns SUCCESS, routes back to the **in-flow reviewer** (e.g., ReviewBrd).
5. When the in-flow reviewer APPROVEs and `fbr_return_pending` is true, the FBR intercept in `StepHandler.__call__` overrides the next node to `FBR_BrdCheck`, re-entering the gauntlet from the top.
6. `fbr_return_pending` is cleared on re-entry to FBR_BrdCheck.

### FAIL
1. `main_retry_count` is incremented.
2. If `max_conditional_per_node` was exceeded (CONDITIONAL escalated to FAIL), same path.
3. Job rewinds to the paired WORK node (e.g., FBR_BrdCheck -> WriteBrd).
4. Downstream conditional counters are reset.
5. The job re-walks the happy path from the rewind target. It will pass through in-flow review again, then re-enter FBR.

Note: CONDITIONAL escalation to FAIL happens when `conditional_counts[gate]` reaches `max_conditional_per_node` (default 3). At that point the CONDITIONAL is treated as FAIL.

## FBR_EvidenceAudit (Terminal Gate)

FBR_EvidenceAudit is not in `FBR_ROUTING`. It has no response node and no rewind target.

- **APPROVE**: Advances to COMPLETE.
- **FAIL**: Immediate DEAD_LETTER. It's in `TERMINAL_FAIL_NODES`. No retry, no rewind. If traceability is broken at this point, the entire RE attempt is suspect and requires human triage.
- **CONDITIONAL**: Not a valid outcome for this gate. The blueprint enforces APPROVED/REJECTED only.

## The fbr_return_pending Flag

This flag exists because FBR gates reuse the same response nodes as in-flow review. When an FBR gate emits CONDITIONAL:

1. The response node does the fix.
2. The response node's SUCCESS routes back to the **in-flow reviewer** (the only SUCCESS edge for that response node in the transition table).
3. The in-flow reviewer re-reviews.
4. On APPROVE, the step handler checks `fbr_return_pending`. If true, it overrides the normal next-node with `FBR_BrdCheck` to re-enter the gauntlet from the top.

Without this flag, an FBR-triggered fix would resume at the in-flow reviewer's normal successor instead of returning to FBR.
