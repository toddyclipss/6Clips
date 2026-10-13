import asyncio
import json
import websockets
import pytest
import aiohttp

WS_URL = "ws://127.0.0.1:16888/ws/chat"
HTTP_BASE = "http://127.0.0.1:16888"

@pytest.mark.asyncio
async def test_live_execution_timeline_with_ollama():
    async with websockets.connect(WS_URL) as ws:
        # Step 1: Wait for any initial connect messages
        initial = await ws.recv()
        data = json.loads(initial)
        print("Initial connect msg:", data.get("type"))

        # Step 2: Send chat message triggering tool execution
        payload = {
            "type": "chat_message",
            "content": "search catalog for title",
            "provider": "ollama",
            "model": "gemma4:e4b",
            "reasoning_level": "low",
        }
        await ws.send(json.dumps(payload))

        tool_events = []
        chat_tokens = []
        chat_done = None
        session_id = None

        # Listen for up to 60 seconds
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < 60:
            try:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                msg = json.loads(msg_raw)
                msg_type = msg.get("type")

                if msg_type == "session_created":
                    session_id = msg.get("session_id")
                    print(f"Session created: {session_id}")

                elif msg_type == "tool_event":
                    print(f"Captured tool_event: tool={msg.get('tool_name')} state={msg.get('state')} duration={msg.get('duration_ms')}ms")
                    tool_events.append(msg)

                elif msg_type == "chat_token":
                    chat_tokens.append(msg.get("token", ""))

                elif msg_type == "chat_done":
                    chat_done = msg
                    print(f"Chat done received! Timeline count: {len(msg.get('execution_timeline') or [])}")
                    break

                elif msg_type == "chat_error":
                    pytest.fail(f"Received chat_error: {msg.get('error')}")

            except asyncio.TimeoutError:
                break

        assert chat_done is not None, "chat_done was not received within timeout"
        assert len(tool_events) >= 2, f"Expected at least 2 tool events (start and finish), got {len(tool_events)}"

        executing_event = next((e for e in tool_events if e.get("state") == "executing"), None)
        assert executing_event is not None, "Missing executing tool_event"
        assert executing_event.get("tool_name") == "search_catalog"

        output_event = next((e for e in tool_events if e.get("state") in ("output-available", "output-error")), None)
        assert output_event is not None, "Missing output tool_event"
        assert output_event.get("duration_ms") is not None
        assert output_event.get("duration_ms") >= 0

        # Verify chat_done contains execution_timeline
        timeline = chat_done.get("execution_timeline")
        assert timeline is not None, "chat_done missing execution_timeline"
        assert len(timeline) >= 1
        assert timeline[0]["tool_calls"][0]["name"] == "search_catalog"

        # Verify persistence via HTTP API
        if session_id:
            await asyncio.sleep(1.0)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{HTTP_BASE}/api/chat/sessions/{session_id}/messages") as resp:
                    assert resp.status == 200
                    messages = await resp.json()
                    assistant_msg = next((m for m in messages if m["role"] == "assistant"), None)
                    assert assistant_msg is not None, "Assistant message was not persisted"
                    assert assistant_msg.get("data_json") is not None, "Assistant message data_json is None"
                    persisted_data = json.loads(assistant_msg["data_json"])
                    assert "execution_timeline" in persisted_data
                    persisted_timeline = persisted_data["execution_timeline"]
                    assert len(persisted_timeline) >= 1
                    assert persisted_timeline[0]["tool_calls"][0]["name"] == "search_catalog"
                    print("PERSISTENCE CHECK PASSED: execution_timeline successfully verified in database!")

if __name__ == "__main__":
    asyncio.run(test_live_execution_timeline_with_ollama())
