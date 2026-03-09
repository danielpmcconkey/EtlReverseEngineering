---
phase: 3
slug: tier-3-append-mode
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Proofmark (custom, `/workspace/proofmark`) |
| **Config file** | Per-job YAML in `/workspace/EtlReverseEngineering/proofmark-configs/` |
| **Quick run command** | Proofmark single-job comparison via `control.proofmark_test_queue` |
| **Full suite command** | Queue all 1196 comparisons (13 jobs x 92 dates) and verify PASS |
| **Estimated runtime** | ~10-15 min for full suite (dependent on queue contention) |

---

## Sampling Rate

- **After every job completion:** Verify 92/92 PASS in `control.proofmark_test_queue`
- **After every plan wave:** Verify all jobs in wave are 92/92 PASS
- **Before `/gsd:verify-work`:** Full 1196/1196 PASS (13 x 92)
- **Max feedback latency:** ~60 seconds per single-job Proofmark run

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-WW-NN | WW | W | COMP-03 | integration | Proofmark queue + verify 92/92 | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Note: Per-task rows will be filled when PLAN.md files define specific task IDs.*

---

## Wave 0 Requirements

- [ ] Fix `re-blueprint.md` sequencing constraint (between steps 7 and 8) — config files must be verified on disk before task queuing
- [ ] Per-job: RE job conf YAML (created during execution)
- [ ] Per-job: Proofmark config YAML (created during execution)
- [ ] No framework changes needed — Append mode, additionalFilter, mostRecent all supported

*Wave 0 is the blueprint fix. All other config files are created per-job during execution.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cumulative output growth | COMP-03 SC-3 | Proofmark validates byte-identical match, but cumulative growth is an additional semantic check | Spot-check 2-3 jobs: compare row counts at dates 1, 46, 92 — should monotonically increase |
| Chronological execution | COMP-03 SC-2 | Framework enforces via advisory locks, but verification is observational | Check `control.task_queue` for date ordering per job — all 92 dates should complete in order |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
