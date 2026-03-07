import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


def _install_sdk_stubs():
    """Install minimal stubs for optional SDK dependencies."""
    if "claude_agent_sdk" not in sys.modules:
        sdk_stub = types.ModuleType("claude_agent_sdk")
        sdk_stub.ClaudeAgentOptions = object
        sdk_stub.query = lambda *args, **kwargs: None
        sys.modules["claude_agent_sdk"] = sdk_stub

    if "langchain_core.messages" not in sys.modules:
        messages_stub = types.ModuleType("langchain_core.messages")
        messages_stub.HumanMessage = object
        messages_stub.SystemMessage = object
        sys.modules["langchain_core.messages"] = messages_stub

    if "langchain_openai" not in sys.modules:
        openai_stub = types.ModuleType("langchain_openai")
        openai_stub.ChatOpenAI = object
        sys.modules["langchain_openai"] = openai_stub

    if "langchain_google_genai" not in sys.modules:
        genai_stub = types.ModuleType("langchain_google_genai")
        genai_stub.ChatGoogleGenerativeAI = object
        sys.modules["langchain_google_genai"] = genai_stub

    if "src.plugins.prompt_fragments" not in sys.modules:
        fragments_stub = types.ModuleType("src.plugins.prompt_fragments")
        fragments_stub.get_prompt_fragment = lambda *_args, **_kwargs: ""
        sys.modules["src.plugins.prompt_fragments"] = fragments_stub

    if "src.cost.tracker" not in sys.modules:
        tracker_stub = types.ModuleType("src.cost.tracker")
        tracker_stub.cost_tracker = object()
        sys.modules["src.cost.tracker"] = tracker_stub
    else:
        tracker_stub = sys.modules["src.cost.tracker"]

    if "src.cost" not in sys.modules:
        cost_stub = types.ModuleType("src.cost")
        cost_stub.tracker = tracker_stub
        sys.modules["src.cost"] = cost_stub

    if "src.db" not in sys.modules:
        sys.modules["src.db"] = types.ModuleType("src.db")

    if "src.db.pool" not in sys.modules:
        pool_stub = types.ModuleType("src.db.pool")
        pool_stub.AsyncSQLitePool = object
        sys.modules["src.db.pool"] = pool_stub

    if "src.db.sqlite_store" not in sys.modules:
        store_stub = types.ModuleType("src.db.sqlite_store")
        store_stub.SQLiteStore = object
        sys.modules["src.db.sqlite_store"] = store_stub

    if "langgraph" not in sys.modules:
        sys.modules["langgraph"] = types.ModuleType("langgraph")

    if "langgraph.checkpoint" not in sys.modules:
        sys.modules["langgraph.checkpoint"] = types.ModuleType("langgraph.checkpoint")

    if "langgraph.checkpoint.memory" not in sys.modules:
        memory_stub = types.ModuleType("langgraph.checkpoint.memory")
        memory_stub.MemorySaver = object
        sys.modules["langgraph.checkpoint.memory"] = memory_stub

    if "langgraph.graph" not in sys.modules:
        graph_stub = types.ModuleType("langgraph.graph")
        graph_stub.END = "END"
        graph_stub.START = "START"

        class _StateGraph:
            def __init__(self, *_args, **_kwargs):
                self.nodes = []

        graph_stub.StateGraph = _StateGraph
        sys.modules["langgraph.graph"] = graph_stub


@pytest.mark.asyncio
async def test_safe_node_uses_default_timeout(monkeypatch):
    _install_sdk_stubs()

    from src.orchestrator import graph
    from src.orchestrator.state import NexusState

    async def _node_fn(state):
        return {"result": state.directive}

    captured = {}

    async def fake_wait_for(coro, timeout):
        captured["timeout"] = timeout
        return await coro

    monkeypatch.setattr(graph.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(graph.CheckpointManager, "save_checkpoint", lambda *_args, **_kwargs: None)

    state = NexusState(directive="timeout-check", project_path="/tmp")
    result = await graph.safe_node(_node_fn, state)

    assert result == {"result": "timeout-check"}
    assert captured["timeout"] == 7200


@pytest.mark.asyncio
async def test_safe_node_honors_custom_timeout(monkeypatch):
    _install_sdk_stubs()

    from src.orchestrator import graph
    from src.orchestrator.state import NexusState

    async def _node_fn(state):
        return {"phase": state.current_phase}

    captured = {}

    async def fake_wait_for(coro, timeout):
        captured["timeout"] = timeout
        return await coro

    monkeypatch.setattr(graph.asyncio, "wait_for", fake_wait_for)
    monkeypatch.setattr(graph.CheckpointManager, "save_checkpoint", lambda *_args, **_kwargs: None)

    state = NexusState(project_path="/tmp")
    result = await graph.safe_node(_node_fn, state, timeout=1337)

    assert result["phase"] == "intake"
    assert captured["timeout"] == 1337


@pytest.mark.asyncio
async def test_start_docker_sets_model_and_tmpfs(monkeypatch, tmp_path):
    from src.sessions import cli_pool

    session = cli_pool.CLISession("thread-x", str(tmp_path))
    captured = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return MagicMock()

    monkeypatch.setattr(cli_pool.asyncio, "create_subprocess_exec", fake_exec)

    await session._start_docker()

    args = list(captured["args"])
    arg_str = " ".join(args)
    assert "NEXUS_CLI_MODEL=sonnet" in arg_str
    assert "NEXUS_CLI_TIMEOUT" not in arg_str
    assert "/home/nexus/.claude" in arg_str


@pytest.mark.asyncio
async def test_cli_session_stall_uses_default_timeout(monkeypatch):
    from src.sessions import cli_pool

    session = cli_pool.CLISession("thread-stall", "/tmp")

    async def fake_start():
        session.process = MagicMock()
        session.process.stdin = MagicMock()
        session.process.stdin.write = MagicMock()
        session.process.stdin.drain = AsyncMock()
        session.process.stdin.close = MagicMock()
        session.process.stdout = MagicMock()
        session.process.stderr = MagicMock()
        session.process.returncode = None
        session.process.kill = MagicMock()
        session.process.wait = AsyncMock()
        return True

    session.start = fake_start

    class FakeMonotonic:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            if self.calls <= 4:
                return 0
            return 7200

    monkeypatch.setattr(cli_pool.time, "monotonic", FakeMonotonic())

    result = await session.send("do work")

    assert result.status == "timeout"
    assert "120" in result.output
    assert "no output" in result.output
