import bot as bot_module


def test_step_handlers_includes_new_self_hosted_steps():
    assert bot_module.STEP_HANDLERS["awaiting_setup_mode"] is bot_module.handle_setup_mode
    assert bot_module.STEP_HANDLERS["awaiting_server_ip"] is bot_module.handle_server_ip


def test_step_handlers_still_includes_existing_steps():
    assert bot_module.STEP_HANDLERS["awaiting_vultr_key"] is bot_module.handle_vultr_key
    assert bot_module.STEP_HANDLERS["confirming"] is bot_module.handle_confirmation
    assert bot_module.STEP_HANDLERS["delete_awaiting_key"] is bot_module.handle_delete_key
