"""The Evolus client, driven against a fake Evolus so the wire format is what is tested."""

import json
from typing import Any

import httpx
import pytest

from byb_agent.evolus import Evolus, EvolusError


class Recorder:
    """Answers with the Nth reply, and keeps what it was asked."""

    def __init__(self, replies: list[tuple[int, dict[str, Any], dict[str, str]]]) -> None:
        self.requests: list[httpx.Request] = []
        self.bodies: list[bytes] = []
        self._replies = replies

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.bodies.append(request.read())
        status, body, headers = self._replies[min(len(self.requests) - 1, len(self._replies) - 1)]
        return httpx.Response(status, json=body, headers=headers)

    @property
    def first(self) -> httpx.Request:
        assert self.requests, "the client never reached Evolus"
        return self.requests[0]

    @property
    def body(self) -> bytes:
        return self.bodies[0]


def evolus_for(settings, *replies: tuple[int, dict[str, Any], dict[str, str]]) -> tuple[Evolus, Recorder]:
    recorder = Recorder(list(replies) or [(200, {}, {})])
    return Evolus(httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler)), settings), recorder


async def test_chat_uses_the_openai_shape_and_the_agent_model(settings):
    evolus, seen = evolus_for(settings, (200, {"choices": [{"message": {"content": "It fits."}}]}, {"x-conversation-id": "conv-77"}))
    answer, conversation = await evolus.ask("does it fit?")
    assert (answer, conversation) == ("It fits.", "conv-77")
    request = seen.first
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk_test"
    payload = json.loads(request.read())
    assert payload["model"] == "space-1:agent-1"
    assert payload["messages"][-1] == {"role": "user", "content": "does it fit?"}


async def test_an_existing_conversation_is_carried_on(settings):
    evolus, seen = evolus_for(settings, (200, {"choices": [{"message": {"content": "0.9 m"}}]}, {}))
    await evolus.ask("and the walkway?", conversation_id="conv-1")
    assert seen.first.headers["x-conversation-id"] == "conv-1"


async def test_chat_without_an_agent_id_refuses_instead_of_guessing(settings):
    settings.evolus_agent_id = ""
    evolus, seen = evolus_for(settings)
    with pytest.raises(EvolusError, match="agent id"):
        await evolus.ask("hello")
    assert seen.requests == []


async def test_rest_calls_carry_the_workspace_headers(settings):
    evolus, seen = evolus_for(settings, (200, {"output": "passer"}, {}))
    assert await evolus.run_tool("translate", "spatzer", {"language": "de"}) == "passer"
    request = seen.first
    assert request.url.path == "/api/v1/ai-tools/translate/run"
    assert request.headers["x-apikey"] == "sk_test"
    assert request.headers["x-application-id"] == "space-1"
    assert json.loads(request.read()) == {"text": "spatzer", "options": {"language": "de"}}


async def test_a_workflow_starts_as_a_form_and_answers_with_the_execution_id(settings):
    evolus, seen = evolus_for(settings, (202, {"executionId": "exec-9", "traceId": "trace-9"}, {}))
    result = await evolus.execute_workflow(
        "wf-1", "a linen sofa for a 4.2 x 3.4 room", params={"band": "$$"}, callback_url="https://example.test/agent/webhooks/evolus?run=r1"
    )
    assert result["executionId"] == "exec-9"
    request = seen.first
    assert request.url.path == "/api/v1/workflows/wf-1/execute"
    assert request.headers["content-type"].startswith("multipart/form-data")
    body = request.read().decode()
    assert 'name="input"' in body and "linen sofa" in body
    assert 'name="parameters"' in body and '"band": "$$"' in body
    assert 'name="callbackUrl"' in body and "run=r1" in body


async def test_a_room_photo_travels_with_the_workflow_it_starts(settings):
    evolus, seen = evolus_for(settings, (202, {"executionId": "exec-10"}, {}))
    await evolus.execute_workflow("wf-1", "my living room", files={"file": ("room.jpg", b"\xff\xd8\xffimage", "image/jpeg")})
    body = seen.first.read().decode(errors="ignore")
    assert 'name="file"' in body and "room.jpg" in body and 'name="input"' in body


async def test_an_execution_is_polled_by_id(settings):
    evolus, seen = evolus_for(settings, (200, {"status": "Completed", "output": {"verdict": "fits"}}, {}))
    result = await evolus.workflow_execution("wf-1", "exec-9")
    assert result["status"] == "Completed"
    assert seen.first.url.path == "/api/v1/workflows/wf-1/executions/exec-9"


async def test_a_library_document_is_uploaded_as_a_file(settings):
    evolus, seen = evolus_for(settings, (200, {"id": "doc-1"}, {}))
    await evolus.index_document("lib-1", "returns-policy.md", b"# Returns\n30 days.")
    request = seen.first
    assert request.url.path.startswith("/api/v1/memories/lib-1/documents")
    assert "returns-policy.md" in request.read().decode()


async def test_workspace_credits_running_out_is_said_loudly(settings):
    evolus, _ = evolus_for(settings, (402, {"detail": "no credits"}, {}))
    with pytest.raises(EvolusError, match="credits"):
        await evolus.run_tool("simplify", "text")


async def test_a_refused_call_says_which_one(settings):
    evolus, _ = evolus_for(settings, (500, {"detail": "boom"}, {}))
    with pytest.raises(EvolusError, match="ai-tools"):
        await evolus.run_tool("simplify", "text")


async def test_a_closed_network_is_a_refusal_too(settings):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    evolus = Evolus(httpx.AsyncClient(transport=httpx.MockTransport(refuse)), settings)
    with pytest.raises(EvolusError, match="failed"):
        await evolus.run_tool("simplify", "text")


async def test_no_credentials_is_a_clean_refusal(settings):
    settings.evolus_api_key = ""
    settings.evolus_app_id = ""
    evolus, seen = evolus_for(settings)
    assert not evolus.credentials
    assert evolus.agent_model is None
    with pytest.raises(EvolusError, match="not configured"):
        await evolus.run_tool("simplify", "text")
    assert seen.requests == []
