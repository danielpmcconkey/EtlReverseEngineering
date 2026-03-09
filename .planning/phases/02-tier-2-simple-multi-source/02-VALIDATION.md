---
phase: 2
slug: tier-2-simple-multi-source
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Proofmark (Python, queue-driven) |
| **Config file** | Per-job YAML in `proofmark-configs/` |
| **Quick run command** | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key = '{JobName}' GROUP BY result;"` |
| **Full suite command** | `PGPASSWORD=claude psql -h 172.18.0.1 -U claude -d atc -c "SELECT job_key, result, COUNT(*) FROM control.proofmark_test_queue WHERE job_key IN ('CardStatusSnapshot','CustomerAccountSummary','SecuritiesDirectory','CardAuthorizationSummary','FeeWaiverAnalysis','TopHoldingsByValue','TransactionSizeBuckets','AccountOverdraftHistory','PreferenceChangeCount','TopBranches') GROUP BY job_key, result ORDER BY job_key, result;"` |
| **Estimated runtime** | ~5 seconds (DB queries) |

---

## Sampling Rate

- **After every task commit:** Verify `task_queue` status for current batch (all Succeeded)
- **After every plan wave:** Verify `proofmark_test_queue` results for current batch (92/92 PASS per job)
- **Before `/gsd:verify-work`:** Full suite must show 920/920 PASS (10 jobs x 92 dates)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| Per-job | 01-10 | 1 | RE-04 | integration | Task queue Succeeded for 92 dates | N/A (DB) | pending |
| Per-job | 01-10 | 1 | RE-08 | integration | Per-job Proofmark query | N/A (DB) | pending |
| Per-job | 01-10 | 1 | RE-01 | manual | Check `jobs/{JobName}/BRD.md` exists | Wave 0 | pending |
| Per-job | 01-10 | 1 | RE-02 | manual | Check `jobs/{JobName}/FSD.md` exists | Wave 0 | pending |
| Per-job | 01-10 | 1 | RE-07 | integration | Proofmark queue returns results | N/A (DB) | pending |
| All jobs | ALL | ALL | COMP-02 | integration | Full suite query | N/A (DB) | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] 10 Proofmark config YAMLs (4 Parquet, 6 CSV)
- [ ] 10 job conf JSONs in `job-confs/`
- [ ] 10 job doc directories in `jobs/`
- [ ] Verify Parquet Proofmark comparison works end-to-end (first Parquet job is the test)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| BRD exists per job | RE-01 | File presence check | `ls jobs/{JobName}/BRD.md` |
| FSD exists per job | RE-02 | File presence check | `ls jobs/{JobName}/FSD.md` |
| Test strategy per job | RE-03 | File presence check | `ls jobs/{JobName}/TestStrategy.md` |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
