import os

os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.pop("LOG_CHANNEL_ID", None)

import pytest


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, embed=None, files=None):
        self.sent.append({"content": content, "embed": embed, "files": files})


class FakeUser:
    def __init__(self, user_id=12345, display_name="tester"):
        self.id = user_id
        self.display_name = display_name
        self.channel = FakeChannel()

    async def send(self, content=None, embed=None, files=None):
        self.channel.sent.append({"content": content, "embed": embed, "files": files})


class FakeMessage:
    def __init__(self, content, author):
        self.content = content
        self.author = author
        self.channel = author.channel


@pytest.fixture
def fake_user():
    return FakeUser()


@pytest.fixture
def fake_message(fake_user):
    def _make(content):
        return FakeMessage(content, fake_user)
    return _make
