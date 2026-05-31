import pytest
from fastmcp.client import Client
from main.server import mcp


@pytest.fixture
async def client():
    async with Client(transport=mcp) as c:
        yield c
