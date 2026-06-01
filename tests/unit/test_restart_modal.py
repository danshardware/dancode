def test_restart_options_fields():
    """RestartOptions carries all submitted fields."""
    from dancode.widgets.restart_modal import RestartOptions
    msg = RestartOptions("t1", 2, "steering", False)
    assert msg.task_id == "t1"
    assert msg.restart_phase == 2
    assert msg.steering_text == "steering"
    assert msg.clear_history is False


def test_restart_modal_instantiation():
    """RestartModal can be instantiated with valid arguments."""
    from dancode.widgets.restart_modal import RestartModal
    modal = RestartModal("t1", "feat", 4, "desc")
    assert modal._task_id == "t1"
    assert modal._feature_name == "feat"
    assert modal._current_phase == 4
    assert modal._feature_description == "desc"


def test_restart_modal_bindings():
    """RestartModal has escape and ctrl+s bindings."""
    from dancode.widgets.restart_modal import RestartModal
    keys = {b.key for b in RestartModal.BINDINGS}
    assert "escape" in keys
    assert "ctrl+s" in keys