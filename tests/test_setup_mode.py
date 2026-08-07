import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_disclaimer_agree_moves_to_setup_mode_selection(fake_message):
    state = {"step": "awaiting_disclaimer", "data": {}}
    msg = fake_message("同意")
    await bot_module.handle_disclaimer(msg, state)
    assert state["step"] == "awaiting_setup_mode"
    last = msg.channel.sent[-1]["embed"]
    assert any("選擇架設方式" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_choose_vultr(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("1")
    await bot_module.handle_setup_mode(msg, state)
    assert state["data"]["mode"] == "vultr"
    assert state["step"] == "awaiting_vultr_key"
    last = msg.channel.sent[-1]["embed"]
    assert any("Vultr" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_choose_self_hosted(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("2")
    await bot_module.handle_setup_mode(msg, state)
    assert state["data"]["mode"] == "self_hosted"
    assert state["step"] == "awaiting_server_ip"
    last = msg.channel.sent[-1]["embed"]
    assert any("伺服器 IP" in f.name for f in last.fields)


@pytest.mark.asyncio
async def test_setup_mode_invalid_input_stays_and_warns(fake_message):
    state = {"step": "awaiting_setup_mode", "data": {}}
    msg = fake_message("3")
    await bot_module.handle_setup_mode(msg, state)
    assert state["step"] == "awaiting_setup_mode"
    assert "mode" not in state["data"]
    assert msg.channel.sent[-1]["content"] is not None
