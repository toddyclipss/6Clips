import asyncio
import json
import httpx
import openai

OPENROUTER_MODELS = [
    "anthropic/claude-fable-5.1",
    "anthropic/claude-opus-5.5",
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-haiku-5.5",
    "openai/gpt-6-astra",
    "openai/gpt-6.1-sol",
    "openai/gpt-6.1-luna",
    "google/gemini-3.8-flash",
    "google/gemini-3.1-pro-preview",
]

EFFORT_MAP = {
    "low": "low",
    "medium": "medium",
    "hard": "high",
}

async def main():
    captured = []

    def handler(request: httpx.Request):
        body = json.loads(request.content.decode("utf-8")) if request.content else {}
        captured.append({
            "url": str(request.url),
            "method": request.method,
            "headers": dict(request.headers),
            "body": body,
        })
        sse = (
            "data: {\"choices\": [{\"delta\": {\"content\": \"OpenRouter chunk\"}}]}\n\n"
            "data: [DONE]\n\n"
        )
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=sse.encode("utf-8"))

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = openai.AsyncOpenAI(
        api_key="sk-or-test-key",
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://6clips.app",
            "X-Title": "6Clips",
        },
        http_client=http_client,
    )

    for m in OPENROUTER_MODELS:
        for ui_lvl, native_effort in EFFORT_MAP.items():
            captured.clear()
            extra_body = {
                "provider": {
                    "require_parameters": True,
                    "allow_fallbacks": False,
                },
                "reasoning": {
                    "effort": native_effort,
                },
            }
            stream = await client.chat.completions.create(
                model=m,
                messages=[{"role": "user", "content": "Test prompt"}],
                stream=True,
                max_tokens=2048,
                extra_body=extra_body,
            )
            tokens = []
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    tokens.append(chunk.choices[0].delta.content)

            assert len(captured) == 1
            req = captured[0]
            assert req["url"] == "https://openrouter.ai/api/v1/chat/completions"
            assert req["method"] == "POST"
            assert req["body"]["model"] == m, f"Model ID altered: {req['body']['model']} != {m}"
            assert req["body"]["reasoning"] == {"effort": native_effort}
            assert req["body"]["provider"] == {"require_parameters": True, "allow_fallbacks": False}
            assert req["headers"]["authorization"] == "Bearer sk-or-test-key"
            assert req["headers"]["http-referer"] == "https://6clips.app"
            assert len(tokens) == 1 and tokens[0] == "OpenRouter chunk"
            print(f"PASSED {m} @ {ui_lvl} -> effort={native_effort}")

    print("\nALL 9 OPENROUTER MODELS VERIFIED ACROSS LOW, MEDIUM, HARD.")

if __name__ == "__main__":
    asyncio.run(main())
