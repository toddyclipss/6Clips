import asyncio
import json
import httpx2
import anthropic

async def main():
    models = [
        "claude-fable-5-1",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    ]
    efforts = ["low", "medium", "high"]

    captured = []

    def handler(request: httpx2.Request):
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        captured.append({
            "url": str(request.url),
            "method": request.method,
            "body": body,
        })
        # Mock SSE stream for anthropic
        sse_text = (
            "event: message_start\ndata: {\"type\": \"message_start\", \"message\": {\"id\": \"msg_1\", \"type\": \"message\", \"role\": \"assistant\", \"content\": [], \"model\": \"claude\", \"stop_reason\": null, \"stop_sequence\": null, \"usage\": {\"input_tokens\": 10, \"output_tokens\": 5}}}\n\n"
            "event: content_block_start\ndata: {\"type\": \"content_block_start\", \"index\": 0, \"content_block\": {\"type\": \"text\", \"text\": \"\"}}\n\n"
            "event: content_block_delta\ndata: {\"type\": \"content_block_delta\", \"index\": 0, \"delta\": {\"type\": \"text_delta\", \"text\": \"Anthropic verified.\"}}\n\n"
            "event: content_block_stop\ndata: {\"type\": \"content_block_stop\", \"index\": 0}\n\n"
            "event: message_delta\ndata: {\"type\": \"message_delta\", \"delta\": {\"stop_reason\": \"end_turn\", \"stop_sequence\": null}, \"usage\": {\"output_tokens\": 15}}\n\n"
            "event: message_stop\ndata: {\"type\": \"message_stop\"}\n\n"
        )
        return httpx2.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse_text.encode("utf-8"))

    transport = httpx2.MockTransport(handler)
    http_client = httpx2.AsyncClient(transport=transport)
    client = anthropic.AsyncAnthropic(api_key="sk-ant-test", http_client=http_client)

    for m in models:
        for eff in efforts:
            captured.clear()
            async with client.messages.stream(
                model=m,
                max_tokens=4096,
                system="You are 6Clips assistant.",
                messages=[{"role": "user", "content": "Test prompt"}],
                extra_body={"output_config": {"effort": eff}},
            ) as stream:
                text = await stream.get_final_text()

            assert len(captured) == 1
            req = captured[0]
            assert req["url"] == "https://api.anthropic.com/v1/messages"
            assert req["method"] == "POST"
            assert req["body"]["model"] == m
            assert req["body"]["max_tokens"] == 4096
            assert req["body"]["output_config"] == {"effort": eff}
            assert "thinking" not in req["body"], "Must not use legacy thinking.budget_tokens on models that reject it"
            print(f"PASSED {m} @ {eff}: output_config.effort={eff}")

    print("ALL ANTHROPIC MODELS & EFFORTS VERIFIED SUCCESSFULLY.")

if __name__ == "__main__":
    asyncio.run(main())
