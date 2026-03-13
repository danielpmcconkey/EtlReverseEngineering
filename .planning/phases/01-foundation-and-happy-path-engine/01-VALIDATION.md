---
phase: 1
slug: foundation-and-happy-path-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — Wave 0 creates pyproject.toml with [tool.pytest.ini_options] |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | SM-01 | unit | `python -m pytest tests/test_models.py::test_job_state_fields -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | SM-02 | unit | `python -m pytest tests/test_transitions.py::test_table_is_dict -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | SM-03 | unit | `python -m pytest tests/test_models.py::test_engine_config_defaults -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | HP-01 | integration | `python -m pytest tests/test_engine.py::test_happy_path_traversal -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | HP-02 | unit | `python -m pytest tests/test_nodes.py::test_stubs_have_descriptions -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 1 | HP-03 | unit | `python -m pytest tests/test_nodes.py::test_work_stub_outcomes -x` | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 1 | HP-04 | unit | `python -m pytest tests/test_nodes.py::test_review_stub_outcomes -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 1 | ENG-01 | integration | `python -m pytest tests/test_engine.py::test_engine_loop -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 1 | ENG-02 | integration | `python -m pytest tests/test_engine.py::test_n_jobs -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 1 | ENG-03 | unit | `python -m pytest tests/test_models.py::test_job_state_is_dataclass -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 1 | ENG-04 | integration | `python -m pytest tests/test_engine.py::test_sequential_execution -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | LOG-01 | unit | `python -m pytest tests/test_logging.py::test_json_output -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | LOG-02 | integration | `python -m pytest tests/test_engine.py::test_transition_logging -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 1 | LOG-03 | integration | `python -m pytest tests/test_engine.py::test_log_completeness -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 1 | PS-01 | smoke | `python -c "import workflow_engine"` | ❌ W0 | ⬜ pending |
| 1-04-02 | 04 | 1 | PS-02 | smoke | `python -m pytest tests/test_models.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — project config with [tool.pytest.ini_options]
- [ ] `src/workflow_engine/__init__.py` — package init
- [ ] `tests/__init__.py` — test package init
- [ ] `tests/conftest.py` — shared fixtures (default EngineConfig, fresh JobState factory)
- [ ] `tests/test_models.py` — SM-01, SM-03, ENG-03
- [ ] `tests/test_transitions.py` — SM-02
- [ ] `tests/test_nodes.py` — HP-02, HP-03, HP-04
- [ ] `tests/test_engine.py` — HP-01, ENG-01, ENG-02, ENG-04, LOG-02, LOG-03
- [ ] `tests/test_logging.py` — LOG-01

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
