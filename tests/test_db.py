"""Integration tests for the Postgres DB layer (task queue + job state)."""

import pytest
import psycopg

from tests.conftest import make_test_job_id

from workflow_engine.db import (
    claim_task,
    complete_task,
    enqueue_task,
    fail_task,
    get_pool,
    is_clutch_engaged,
    load_job_state,
    save_job_state,
)
from workflow_engine.models import JobState


# -- Pool tests ---------------------------------------------------------------


class TestPool:
    def test_get_pool_returns_pool(self):
        pool = get_pool()
        with pool.connection() as conn:
            row = conn.execute("SELECT 1 AS n").fetchone()
        assert row is not None and row[0] == 1


# -- Task queue tests ---------------------------------------------------------


class TestEnqueueTask:
    def test_enqueue_returns_id(self):
        jid = make_test_job_id("enq")
        task_id = enqueue_task(jid, "LocateOgSourceFiles")
        assert isinstance(task_id, int)
        assert task_id > 0

    def test_enqueue_duplicate_active_raises(self):
        jid = make_test_job_id("dup")
        enqueue_task(jid, "LocateOgSourceFiles")
        with pytest.raises(psycopg.errors.UniqueViolation):
            enqueue_task(jid, "SomeOtherNode")


class TestClaimTask:
    def test_claim_returns_oldest_pending(self):
        jid1 = make_test_job_id("c1")
        jid2 = make_test_job_id("c2")
        id1 = enqueue_task(jid1, "NodeA")
        _id2 = enqueue_task(jid2, "NodeB")
        claimed = claim_task()
        assert claimed is not None
        assert claimed["id"] == id1
        assert claimed["job_id"] == jid1
        assert claimed["node_name"] == "NodeA"

    def test_claim_returns_none_when_empty(self):
        assert claim_task() is None

    def test_claim_skips_already_claimed(self):
        jid1 = make_test_job_id("s1")
        jid2 = make_test_job_id("s2")
        enqueue_task(jid1, "NodeA")
        enqueue_task(jid2, "NodeB")
        first = claim_task()
        second = claim_task()
        assert first is not None and second is not None
        assert first["job_id"] == jid1
        assert second["job_id"] == jid2


class TestCompleteTask:
    def test_complete_sets_status(self):
        jid = make_test_job_id("comp")
        task_id = enqueue_task(jid, "NodeA")
        claimed = claim_task()
        assert claimed is not None
        complete_task(task_id)
        pool = get_pool()
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT status, completed_at FROM control.re_task_queue WHERE id = %s",
                (task_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == "completed"
        assert row[1] is not None


class TestFailTask:
    def test_fail_sets_status(self):
        jid = make_test_job_id("fail")
        task_id = enqueue_task(jid, "NodeA")
        claim_task()
        fail_task(task_id)
        pool = get_pool()
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT status, completed_at FROM control.re_task_queue WHERE id = %s",
                (task_id,),
            ).fetchone()
        assert row is not None
        assert row[0] == "failed"
        assert row[1] is not None


class TestFifoOrder:
    def test_fifo_ordering(self):
        """Tasks are claimed in creation order."""
        jids = [make_test_job_id(f"fifo{i}") for i in range(3)]
        ids = [enqueue_task(jid, f"Node{i}") for i, jid in enumerate(jids)]
        claimed_ids = []
        for _ in range(3):
            t = claim_task()
            assert t is not None
            claimed_ids.append(t["id"])
            complete_task(t["id"])
        assert claimed_ids == ids


# -- Engine config tests ------------------------------------------------------


class TestClutch:
    def test_clutch_defaults_disengaged(self):
        assert is_clutch_engaged() is False

    def test_clutch_engages(self):
        pool = get_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_engine_config SET clutch_engaged = true WHERE id = 1"
            )
        assert is_clutch_engaged() is True

    def test_clutch_disengages(self):
        pool = get_pool()
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_engine_config SET clutch_engaged = true WHERE id = 1"
            )
        assert is_clutch_engaged() is True
        with pool.connection() as conn:
            conn.execute(
                "UPDATE control.re_engine_config SET clutch_engaged = false WHERE id = 1"
            )
        assert is_clutch_engaged() is False


# -- Job state tests ----------------------------------------------------------


class TestSaveLoadJobState:
    def test_save_and_load(self):
        jid = make_test_job_id("sl")
        state = JobState(job_id=jid, current_node="CheckReview", status="RUNNING")
        save_job_state(state)
        loaded = load_job_state(jid)
        assert loaded is not None
        assert loaded.job_id == jid
        assert loaded.current_node == "CheckReview"
        assert loaded.status == "RUNNING"

    def test_load_nonexistent_returns_none(self):
        assert load_job_state(make_test_job_id("nope")) is None

    def test_upsert_overwrites(self):
        jid = make_test_job_id("upsert")
        state = JobState(job_id=jid)
        save_job_state(state)
        state.current_node = "FullBuildReview"
        state.main_retry_count = 3
        save_job_state(state)
        loaded = load_job_state(jid)
        assert loaded is not None
        assert loaded.current_node == "FullBuildReview"
        assert loaded.main_retry_count == 3

    def test_round_trip_all_fields(self):
        """Every field survives a save/load round trip including nested dicts."""
        jid = make_test_job_id("roundtrip")
        state = JobState(
            job_id=jid,
            current_node="TriageNode",
            status="RUNNING",
            main_retry_count=2,
            conditional_counts={"CheckReview": 1, "FullBuildReview": 3},
            last_rejection_reason="syntax error in line 42",
            fbr_return_pending=True,
            triage_results={"route_a": "pass", "route_b": "fail"},
            triage_rewind_target="LocateOgSourceFiles",
        )
        save_job_state(state)
        loaded = load_job_state(jid)
        assert loaded is not None
        assert loaded.job_id == state.job_id
        assert loaded.current_node == state.current_node
        assert loaded.status == state.status
        assert loaded.main_retry_count == state.main_retry_count
        assert loaded.conditional_counts == state.conditional_counts
        assert loaded.last_rejection_reason == state.last_rejection_reason
        assert loaded.fbr_return_pending == state.fbr_return_pending
        assert loaded.triage_results == state.triage_results
        assert loaded.triage_rewind_target == state.triage_rewind_target
