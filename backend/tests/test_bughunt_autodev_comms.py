"""Bug-hunt tests (TDD RED->GREEN) for auto_dev + communication adapters + lancedb_handler.

Each test in this file was written FIRST (RED), observed failing, then the
corresponding minimal source fix was applied (GREEN). See TESTED_FILES_TRACKER.md.

Bugs covered:
  1. lancedb_handler: vector_columns lost `vector_fastembed` -> FastEmbed dual-vector
     storage dead (embedding_service always gets ValueError).
  2. lancedb_handler: create_table(dual_vector=True) no longer adds the
     vector_fastembed column to the schema.
  3. telegram adapter: normalize_payload violates the PlatformAdapter contract
     (async + (request, body_bytes) vs sync (payload dict)) -> TypeError + leaked
     coroutine for dict-style callers; existing test_adapters_coverage failed.
  4. signal adapter: send_message never inspects HTTP status (raise_for_status
     commented out) -> reports success on 4xx/5xx.
  5. google_chat adapter: send_message creates an httpx client but never sends a
     request -> always reports success, messages never delivered.
  6. evolution_pipeline: daily-limit stage passes (tenant_id, source) to
     check_daily_limits(agent_id, capability, ...) -> capability never matches,
     gate always passes (fail-open no-op).
  7. evolution_pipeline: regression validation stage documented in the module
     docstring but never executed -> behavioral regressions slip through.
  8. container_sandbox: docker timeout kills only the docker CLI client; the
     container itself is orphaned (--rm never runs).
  9. lancedb_handler: get_embedding interpolates episode_id unescaped into the
     where clause (filter injection), unlike get_document_by_id.
  10. lancedb_handler: test_connection leaks str(e) into the response message.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import httpx

from core.auto_dev.evolution_pipeline import (
    MutationRequest,
    UnifiedEvolutionPipeline,
)
from core.auto_dev.regression_validator import RegressionResult, TestMismatch
from core.lancedb_handler import LanceDBHandler
from core.communication.adapters.google_chat import GoogleChatAdapter
from core.communication.adapters.signal import SignalAdapter
from core.communication.adapters.telegram import TelegramAdapter
from core.communication.adapters.teams import TeamsAdapter


# ---------------------------------------------------------------------------
# 1 & 2. lancedb_handler dual-vector storage dead
# ---------------------------------------------------------------------------

def test_vector_columns_include_fastembed(tmp_path):
    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    assert "vector_fastembed" in handler.vector_columns
    assert handler.vector_columns["vector_fastembed"] == 384


def test_create_table_dual_vector_adds_fastembed_column(tmp_path):
    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    handler.db = Mock()
    handler.db.create_table = Mock(return_value=Mock())
    handler._ensure_db = Mock()

    with patch("core.lancedb_handler.pa") as mock_pa:
        mock_pa.field.return_value = "field"
        mock_pa.schema.side_effect = lambda fields: fields
        handler.create_table("episodes", dual_vector=True)

    field_names = [c.args[0] for c in mock_pa.field.call_args_list]
    assert "vector_fastembed" in field_names
    fastembed_call = next(c for c in mock_pa.field.call_args_list if c.args[0] == "vector_fastembed")
    assert fastembed_call.args[1] is not None


# ---------------------------------------------------------------------------
# 11. knowledge_graph tables created with the wrong schema (dead elif branch):
#     create_table('knowledge_graph') always built the plain document schema
#     (no from_id/to_id/type), so add_knowledge_edge inserts fail on schema
#     mismatch and edges never persist.
# ---------------------------------------------------------------------------

def test_create_table_knowledge_graph_has_edge_columns(tmp_path):
    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    handler.db = Mock()
    handler.db.create_table = Mock(return_value=Mock())
    handler._ensure_db = Mock()

    with patch("core.lancedb_handler.pa") as mock_pa:
        mock_pa.field.return_value = "field"
        mock_pa.schema.side_effect = lambda fields: fields
        handler.create_table("knowledge_graph")

    field_names = [c.args[0] for c in mock_pa.field.call_args_list]
    assert "from_id" in field_names
    assert "to_id" in field_names
    assert "type" in field_names
    assert "text" in field_names


def test_add_knowledge_edge_record_is_schema_complete(tmp_path):
    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    handler.db = Mock()
    handler.embedding_service = None
    handler._ensure_db = Mock()
    table = Mock()
    handler.get_table = Mock(return_value=table)
    assert handler.add_knowledge_edge("a", "b", "related", "desc") is True
    record = table.add.call_args.args[0][0]
    assert record["from_id"] == "a"
    assert record["to_id"] == "b"
    assert record["type"] == "related"
    assert "text" in record
    assert "source" in record


# ---------------------------------------------------------------------------
# 3. telegram normalize_payload contract
# ---------------------------------------------------------------------------

def test_telegram_normalize_payload_accepts_payload_dict():
    adapter = TelegramAdapter(bot_token="test")
    payload = {
        "message": {
            "from": {"id": 123, "username": "bob"},
            "chat": {"id": 456},
            "text": "Hello",
        }
    }
    result = adapter.normalize_payload(payload)
    assert isinstance(result, dict)
    assert result["platform"] == "telegram"
    assert result["user_id"] == "123"
    assert result["channel_id"] == "456"
    assert result["username"] == "bob"
    assert result["content"] == "Hello"
    assert result["metadata"] == payload


def test_telegram_normalize_payload_handles_voice_and_empty():
    adapter = TelegramAdapter(bot_token="test")
    payload = {
        "message": {
            "from": {"id": 1},
            "chat": {"id": 2},
            "voice": {"file_id": "FILE"},
        }
    }
    result = adapter.normalize_payload(payload)
    assert result["content"] == "[Voice Message]"
    assert result["metadata"]["media_id"] == "FILE"
    assert result["metadata"]["media_type"] == "voice"

    empty = adapter.normalize_payload({})
    assert isinstance(empty, dict)
    assert empty["user_id"] == ""
    assert empty["content"] == ""
    assert adapter.normalize_payload("not-json") == {}
    assert adapter.normalize_payload(None) == {}


# ---------------------------------------------------------------------------
# 3b. teams normalize_payload contract (same bug class as telegram)
# ---------------------------------------------------------------------------

def test_teams_normalize_payload_accepts_payload_dict():
    adapter = TeamsAdapter(app_id="test", app_password="secret")
    payload = {
        "type": "message",
        "id": "a:1",
        "from": {"id": "user-1", "name": "Alice"},
        "conversation": {"id": "conv-1"},
        "text": "Hello from Teams",
        "serviceUrl": "https://smba.trafficmanager.net/apis",
    }
    result = adapter.normalize_payload(payload)
    assert isinstance(result, dict)
    assert result["platform"] == "teams"
    assert result["user_id"] == "user-1"
    assert result["username"] == "Alice"
    assert result["channel_id"] == "conv-1"
    assert result["content"] == "Hello from Teams"
    assert result["metadata"]["serviceUrl"] == "https://smba.trafficmanager.net/apis"
    assert result["metadata"]["full_data"] == payload


def test_teams_normalize_payload_handles_non_message_and_empty():
    adapter = TeamsAdapter(app_id="test", app_password="secret")
    assert adapter.normalize_payload({"type": "conversationUpdate"}) == {}
    empty = adapter.normalize_payload({})
    assert isinstance(empty, dict)
    assert empty.get("user_id") is None
    assert empty.get("content") is None
    assert adapter.normalize_payload("not-json") == {}
    assert adapter.normalize_payload(None) == {}


# ---------------------------------------------------------------------------
# 4. signal send_message swallows HTTP errors
# ---------------------------------------------------------------------------
def test_signal_send_message_returns_false_on_http_error():
    response = Mock()
    response.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "400 Bad Request", request=Mock(), response=Mock()
        )
    )
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient", return_value=client):
        ok = asyncio.run(SignalAdapter(api_url="http://bridge:8080").send_message("+1234", "hi"))

    assert ok is False
    client.post.assert_awaited_once()


# ---------------------------------------------------------------------------
# 5. google_chat send_message never sends
# ---------------------------------------------------------------------------

def test_google_chat_send_message_posts_to_space():
    response = Mock()
    response.raise_for_status = Mock()
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient", return_value=client):
        ok = asyncio.run(GoogleChatAdapter().send_message("spaces/AAA", "hello"))

    assert ok is True
    assert client.post.await_count == 1
    sent_url = client.post.await_args.args[0]
    assert sent_url == "https://chat.googleapis.com/v1/spaces/AAA/messages"


def test_google_chat_send_message_returns_false_on_error():
    response = Mock()
    response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError("403", request=Mock(), response=Mock()))
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient", return_value=client):
        ok = asyncio.run(GoogleChatAdapter().send_message("spaces/AAA", "hello"))

    assert ok is False


# ---------------------------------------------------------------------------
# 6 & 7. evolution_pipeline safety gates
# ---------------------------------------------------------------------------

def _pipeline_with_governance_ok(db):
    gov = Mock()
    gov.validate_evolution_directive = AsyncMock(return_value=True)
    return gov


def test_pipeline_daily_limit_blocks_with_correct_agent_capability():
    db = Mock()
    gov = _pipeline_with_governance_ok(db)
    gate = Mock()
    gate.check_daily_limits = Mock(return_value=False)

    with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
    ):
        request = MutationRequest(
            agent_id="ag-1",
            tenant_id="t-1",
            source="gea",
            config_key="system_prompt",
            old_value="old",
            new_value="new",
        )
        result = asyncio.run(UnifiedEvolutionPipeline(db).submit_and_deploy(request))

    assert result.passed is False
    assert result.stage == "daily_limit"
    assert gate.check_daily_limits.call_args.args[0] == "ag-1"
    assert gate.check_daily_limits.call_args.args[1] == "auto_dev.alpha_evolver"


def test_pipeline_memento_source_maps_to_memento_capability():
    db = Mock()
    gov = _pipeline_with_governance_ok(db)
    gate = Mock()
    gate.check_daily_limits = Mock(return_value=True)

    with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
    ):
        request = MutationRequest(
            agent_id="ag-2",
            tenant_id="t-1",
            source="memento",
            config_key="system_prompt",
            old_value="old",
            new_value="new",
        )
        asyncio.run(UnifiedEvolutionPipeline(db).submit_and_deploy(request))

    assert gate.check_daily_limits.call_args.args[1] == "auto_dev.memento_skills"


def test_pipeline_regression_stage_rejects_behavioral_change():
    db = Mock()
    gov = _pipeline_with_governance_ok(db)
    gate = Mock()
    gate.check_daily_limits = Mock(return_value=True)
    validator = Mock()
    validator.validate_regression = AsyncMock(
        return_value=RegressionResult(
            passed=False,
            mismatches=[TestMismatch(test_input={}, parent_output="a", child_output="b")],
            total_tests=1,
        )
    )

    with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
    ), patch("core.auto_dev.regression_validator.RegressionValidator", return_value=validator):
        request = MutationRequest(
            agent_id="ag-3",
            tenant_id="t-1",
            source="gea",
            config_key="system_prompt",
            old_value="old",
            new_value="new",
            parent_code="def f(x): return x",
            mutated_code="def f(x): return x + 1",
            test_inputs=[{"x": 1}],
        )
        result = asyncio.run(UnifiedEvolutionPipeline(db).submit_and_deploy(request))

    assert result.passed is False
    assert result.stage == "regression"
    validator.validate_regression.assert_awaited_once()


def test_pipeline_regression_stage_passes_clean_mutation():
    db = Mock()
    gov = _pipeline_with_governance_ok(db)
    gate = Mock()
    gate.check_daily_limits = Mock(return_value=True)
    validator = Mock()
    validator.validate_regression = AsyncMock(
        return_value=RegressionResult(passed=True, total_tests=1, passed_tests=1)
    )

    with patch("core.agent_governance_service.AgentGovernanceService", return_value=gov), patch(
        "core.auto_dev.capability_gate.AutoDevCapabilityService", return_value=gate
    ), patch("core.auto_dev.regression_validator.RegressionValidator", return_value=validator):
        request = MutationRequest(
            agent_id="ag-4",
            tenant_id="t-1",
            source="gea",
            config_key="system_prompt",
            old_value="old",
            new_value="new",
            parent_code="def f(x): return x",
            mutated_code="def f(x): return x",
            test_inputs=[{"x": 1}],
        )
        result = asyncio.run(UnifiedEvolutionPipeline(db).submit_and_deploy(request))

    assert result.passed is True
    assert result.stage == "validated"


# ---------------------------------------------------------------------------
# 8. container_sandbox docker timeout orphans the container
# ---------------------------------------------------------------------------

def test_container_sandbox_docker_timeout_kills_container():
    from core.auto_dev.container_sandbox import ContainerSandbox

    sb = ContainerSandbox(docker_image="python:3.11-slim", timeout=1)
    sb._docker_available = True

    proc = AsyncMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = Mock()
    proc.wait = AsyncMock()
    kill_proc = AsyncMock()

    with patch("asyncio.create_subprocess_exec", side_effect=[proc, kill_proc]) as mock_exec, patch(
        "tempfile.NamedTemporaryFile"
    ) as mock_tmp, patch("os.path.exists", return_value=True), patch(
        "pathlib.Path.read_text", return_value="cid123"
    ):
        mock_tmp.return_value.__enter__.return_value.name = "/tmp/fake_script.py"
        result = asyncio.run(sb.execute_raw_python("t-1", "code()", {}, timeout=1))

    assert result["status"] == "failed"
    assert "timed out" in result["output"]
    assert result["environment"] == "docker"
    assert mock_exec.call_count == 2
    kill_args = mock_exec.call_args_list[1].args
    assert kill_args[0] == "docker"
    assert kill_args[1] == "kill"


def test_container_sandbox_docker_timeout_without_cidfile_still_returns():
    from core.auto_dev.container_sandbox import ContainerSandbox

    sb = ContainerSandbox(docker_image="python:3.11-slim", timeout=1)
    sb._docker_available = True

    proc = AsyncMock()
    proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    proc.kill = Mock()
    proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", side_effect=[proc]) as mock_exec, patch(
        "tempfile.NamedTemporaryFile"
    ) as mock_tmp, patch("os.path.exists", return_value=False):
        mock_tmp.return_value.__enter__.return_value.name = "/tmp/fake_script.py"
        result = asyncio.run(sb.execute_raw_python("t-1", "code()", {}, timeout=1))

    assert result["status"] == "failed"
    assert mock_exec.call_count == 1


# ---------------------------------------------------------------------------
# 9 & 10. lancedb_handler filter injection / str(e) leak
# ---------------------------------------------------------------------------

def test_get_embedding_escapes_episode_id(tmp_path):
    table = Mock()
    table.search = Mock(return_value=table)
    table.limit = Mock(return_value=table)
    empty_pdf = MagicMock()
    empty_pdf.empty = True
    table.to_pandas = Mock(return_value=empty_pdf)

    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    handler.db = Mock()
    handler.db.table_names = Mock(return_value=["episodes"])
    handler.db.open_table = Mock(return_value=table)
    handler._ensure_db = Mock()

    asyncio.run(handler.get_embedding("episodes", "abc'def"))

    where_arg = table.search().where.call_args.args[0]
    assert "abc''def" in where_arg


def test_test_connection_does_not_leak_exception_details(tmp_path):
    handler = LanceDBHandler(db_path=str(tmp_path / "mem"))
    handler.db = Mock()
    handler.db.table_names = Mock(side_effect=RuntimeError("secret-internal-detail"))
    handler._ensure_db = Mock()

    result = handler.test_connection()
    assert result["connected"] is False
    assert "secret-internal-detail" not in result["message"]
