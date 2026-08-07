import pytest

import bot as bot_module


@pytest.mark.asyncio
async def test_twitch_id_step_number_vultr(fake_message):
    state = {"step": "awaiting_twitch_id", "data": {"mode": "vultr"}}
    msg = fake_message("hitorigs")
    await bot_module.handle_twitch_id(msg, state)
    assert state["data"]["twitch_id"] == "hitorigs"
    assert state["step"] == "awaiting_twitch_oauth"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 4") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_id_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_twitch_id", "data": {"mode": "self_hosted"}}
    msg = fake_message("hitorigs")
    await bot_module.handle_twitch_id(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 3") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_oauth_step_number_vultr(fake_message):
    state = {"step": "awaiting_twitch_oauth", "data": {"mode": "vultr"}}
    msg = fake_message("abc123token")
    await bot_module.handle_twitch_oauth(msg, state)
    assert state["data"]["twitch_oauth"] == "abc123token"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 5") for f in last.fields)


@pytest.mark.asyncio
async def test_twitch_oauth_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_twitch_oauth", "data": {"mode": "self_hosted"}}
    msg = fake_message("abc123token")
    await bot_module.handle_twitch_oauth(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 4") for f in last.fields)


@pytest.mark.asyncio
async def test_obs_password_step_number_vultr(fake_message):
    state = {"step": "awaiting_obs_password", "data": {"mode": "vultr"}}
    msg = fake_message("mypassword")
    await bot_module.handle_obs_password(msg, state)
    assert state["data"]["obs_password"] == "mypassword"
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 6") for f in last.fields)


@pytest.mark.asyncio
async def test_obs_password_step_number_self_hosted(fake_message):
    state = {"step": "awaiting_obs_password", "data": {"mode": "self_hosted"}}
    msg = fake_message("mypassword")
    await bot_module.handle_obs_password(msg, state)
    last = msg.channel.sent[-1]["embed"]
    assert any(f.name.startswith("STEP 5") for f in last.fields)
