---
phase: 2
slug: review-branching-and-counter-mechanics
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest, configured in pyproject.toml) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd /workspace/EtlReverseEngineering && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SM-04 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_fail_increments_main_retry -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | SM-05 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_dead_letter_on_max_retries -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | SM-06 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_increments_counter -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | SM-07 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_auto_promotes_to_fail -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | SM-08 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_conditional_resets_on_approve -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 1 | SM-09 | unit | `python -m pytest tests/test_engine.py::TestCounterMechanics::test_downstream_counters_reset_on_rewind -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | RB-01 | unit | `python -m pytest tests/test_transitions.py::TestReviewRouting::test_approve_routes_happy_path -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | RB-02 | integration | `python -m pytest tests/test_engine.py::TestReviewBranching::test_conditional_loop -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | RB-03 | integration | `python -m pytest tests/test_engine.py::TestReviewBranching::test_fail_rewinds_to_write_node -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 1 | RB-04 | unit | `python -m pytest tests/test_engine.py::TestReviewBranching::test_only_latest_rejection_reason -x` | ❌ W0 | ⬜ pending |
| 02-02-05 | 02 | 1 | RB-05 | unit | `python -m pytest tests/test_nodes.py::test_response_nodes_exist -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_engine.py::TestCounterMechanics` — new test class covering SM-04 through SM-09
- [ ] `tests/test_engine.py::TestReviewBranching` — new test class covering RB-01 through RB-04
- [ ] `tests/test_transitions.py::TestReviewRouting` — new tests for expanded transition table
- [ ] `tests/test_nodes.py::test_response_nodes_exist` — verify 7 response nodes in registry

*Existing infrastructure (conftest.py, pytest config) is sufficient. No new framework setup needed.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
