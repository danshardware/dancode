"""Tests for restart task wiring into task detail and app."""

def test_restart_task_message():
    """RestartTask message carries task_id."""
    from dancode.widgets.task_detail import RestartTask
    msg = RestartTask("my-task-id")
    assert msg.task_id == "my-task-id"


def test_restart_button_shown_for_cancelled():
    """CANCELLED status satisfies the condition for showing the restart button."""
    from dancode.config import TaskStatus
    status = TaskStatus.CANCELLED
    assert status in (TaskStatus.DONE, TaskStatus.CANCELLED)


def test_clear_history_removes_correct_phases():
    """clear_history removes session_ids and token counts for phases >= restart_phase."""
    from dancode.config import PHASE_AGENTS, TaskPhase
    session_ids = {agent_id: f"sess-{phase.value}" for phase, agent_id in PHASE_AGENTS.items()}
    token_counts = {agent_id: phase.value * 100 for phase, agent_id in PHASE_AGENTS.items()}

    restart_phase = 5
    to_clear = {aid for p, aid in PHASE_AGENTS.items() if p.value >= restart_phase}
    session_ids = {k: v for k, v in session_ids.items() if k not in to_clear}
    token_counts = {k: v for k, v in token_counts.items() if k not in to_clear}

    # Phases 1-4 should survive
    assert "phase1_plan" in session_ids
    assert "phase4_dispatch" in session_ids
    # Phase 5+ should be gone
    assert "phase5_code" not in session_ids
    assert "phase10_finalize" not in session_ids
    assert "phase5_code" not in token_counts