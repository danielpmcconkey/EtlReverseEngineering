---
phase: 3
slug: fbr-gauntlet-triage-and-validation-run
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 3 — Validation Strategy

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

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | FBR-01 | unit | `pytest tests/test_transitions.py::TestFBRGauntlet::test_fbr_gate_edges_in_transition_table -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 1 | FBR-02 | integration | `pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_conditional_restarts_gauntlet -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | FBR-03 | integration | `pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_fail_rewinds_to_write_node -x` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | FBR-04 | unit | `pytest tests/test_engine.py::TestFBRGauntlet::test_fbr_return_pending_flag -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 1 | TR-01 | unit | `pytest tests/test_transitions.py::TestTriage::test_proofmark_failure_enters_triage -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | TR-02 | unit | `pytest tests/test_nodes.py::TestTriageNodes::test_t1_t2_context_gathering -x` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 1 | TR-03 | unit | `pytest tests/test_nodes.py::TestTriageNodes::test_diagnostic_stubs_record_verdict -x` | ❌ W0 | ⬜ pending |
| 3-02-04 | 02 | 1 | TR-04 | unit | `pytest tests/test_engine.py::TestTriage::test_t7_routes_to_earliest_fault -x` | ❌ W0 | ⬜ pending |
| 3-02-05 | 02 | 1 | TR-05 | unit | `pytest tests/test_engine.py::TestTriage::test_multiple_faults_route_to_earliest -x` | ❌ W0 | ⬜ pending |
| 3-02-06 | 02 | 1 | TR-06 | unit | `pytest tests/test_engine.py::TestTriage::test_no_faults_dead_letter -x` | ❌ W0 | ⬜ pending |
| 3-02-07 | 02 | 1 | TR-07 | unit | `pytest tests/test_engine.py::TestTriage::test_triage_increments_main_retry -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_transitions.py::TestFBRGauntlet` — FBR edge coverage (FBR_ROUTING entries, CONDITIONAL/FAIL edges for all 6 gates)
- [ ] `tests/test_transitions.py::TestTriage` — triage entry edge, T1-T6 advance edges
- [ ] `tests/test_engine.py::TestFBRGauntlet` — FBR-02, FBR-03, FBR-04 behavior tests using ScriptedNode
- [ ] `tests/test_engine.py::TestTriage` — TR-04 through TR-07 using ScriptedNode + direct triage_results setup
- [ ] `tests/test_nodes.py::TestTriageNodes` — TR-02, TR-03 node behavior
- [ ] `tests/test_models.py` — new JobState fields (fbr_return_pending, triage_results, triage_rewind_target)

*Existing infrastructure (conftest.py, ScriptedNode, _capture_logs, pytest config) is fully sufficient. No new framework setup needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 100+ job validation run produces all transition types | SC-5 | Statistical; requires RNG outcomes | Run validation script, inspect logs for rewinds, conditionals, FBR restarts, triage, DEAD_LETTER |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
