---
phase: 1
slug: tier-1-pipeline-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Proofmark (Python, queue-driven) + PostgreSQL queries |
| **Config file** | Per-job YAML in `proofmark-configs/` |
| **Quick run command** | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key = '{JobName}' GROUP BY result;"` |
| **Full suite command** | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT job_key, result, COUNT(*) FROM control.proofmark_test_queue GROUP BY job_key, result ORDER BY job_key, result;"` |
| **Estimated runtime** | ~5 seconds (DB queries) |

---

## Sampling Rate

- **After every task commit:** Run quick command for current job
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must show 92/92 PASS per job
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-XX | 01 | 0 | DELIV-08 | config | Proofmark YAML exists in `proofmark-configs/` | ❌ W0 | ⬜ pending |
| 01-XX-XX | per-job | 1+ | DELIV-04 | integration | `SELECT status, COUNT(*) FROM control.task_queue WHERE job_key='{JobName}' GROUP BY status` | N/A (DB) | ⬜ pending |
| 01-XX-XX | per-job | 1+ | DELIV-08 | integration | Quick run command per job_key | N/A (DB) | ⬜ pending |
| 01-XX-XX | per-job | 1+ | DELIV-01 | manual-only | Check `jobs/{JobName}/BRD.md` exists with numbered reqs | ❌ W0 | ⬜ pending |
| 01-XX-XX | per-job | 1+ | DELIV-02 | manual-only | Check `jobs/{JobName}/FSD.md` exists with traceability | ❌ W0 | ⬜ pending |
| 01-XX-XX | per-job | 1+ | ANTI-01 | manual-only | Check BRD contains AP1-AP10 assessment | ❌ W0 | ⬜ pending |
| 01-XX-XX | all | final | COMP-01 | integration | Full suite: all 3 job_keys show 92 PASS | N/A (DB) | ⬜ pending |
| 01-XX-XX | all | final | PROC-01 | process | Full workflow completes autonomously | N/A (process) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `proofmark-configs/BranchDirectory.yaml` — Proofmark config
- [ ] `proofmark-configs/ComplianceResolutionTime.yaml` — Proofmark config (needs `trailer_rows: 1`)
- [ ] `proofmark-configs/OverdraftFeeSummary.yaml` — Proofmark config
- [ ] `mkdir -p /workspace/MockEtlFramework/Output/curated_re` — RE output directory

*Existing infrastructure covers ETL execution and DB queries.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| BRD exists with numbered reqs | DELIV-01 | Doc artifact, not code | Check `jobs/{JobName}/BRD.md` has numbered requirements |
| FSD exists with traceability | DELIV-02 | Doc artifact, not code | Check `jobs/{JobName}/FSD.md` has req traceability |
| Anti-pattern assessment | ANTI-01 | Requires human judgment on AP1-AP10 | Check BRD anti-pattern section covers all 10 |
| Zero human input | PROC-01 | Process validation | Confirm no human intervention during execution |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
