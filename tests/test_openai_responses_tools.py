import asyncio
import json
import httpx
import openai

async def main():
    captured = []
    
    # First response triggers tool call
    resp_tool_call = {
        "id": "resp_001",
        "output": [
            {
                "type": "function_call",
                "id": "call_abc",
                "call_id": "call_abc",
                "name": "search_catalog",
                "arguments": json.dumps({"query": "cyberpunk"})
            }
        ]
    }
    
    # Second response gives final answer
    resp_final = {
        "id": "resp_002",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "I found the cyberpunk assets."
                    }
                ]
            }
        ]
    }
    
    call_count = 0
    def handler(request: httpx.Request):
        nonlocal call_count
        call_count += 1
        captured.append({
            "url": str(request.url),
            "method": request.method,
            "body": json.loads(request.content.decode("utf-8"))
        })
        if call_count == 1:
            return httpx.Response(200, json=resp_tool_call)
        else:
            return httpx.Response(200, json=resp_final)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = openai.AsyncOpenAI(api_key="sk-test", http_client=http_client)

    tools = [{
        "type": "function",
        "name": "search_catalog",
        "description": "Search catalog",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"]
        }
    }]

    # Round 1
    res1 = await client.responses.create(
        model="gpt-6-astra",
        input=[{"role": "user", "content": "Find cyberpunk assets"}],
        reasoning={"effort": "high"},
        tools=tools,
    )
    print("ROUND 1 CAPTURED:")
    print(json.dumps(captured[0]["body"], indent=2))
    print("OUTPUT ITEMS:", res1.output)

    # Tool execution
    tool_result = {"status": "success", "items": [{"id": "cyber_1", "title": "Cyber City"}]}
    
    # Round 2 continuation
    res2 = await client.responses.create(
        model="gpt-6-astra",
        input=[
            {"role": "user", "content": "Find cyberpunk assets"},
            {
                "type": "function_call",
                "call_id": "call_abc",
                "name": "search_catalog",
                "arguments": json.dumps({"query": "cyberpunk"})
            },
            {
                "type": "function_call_output",
                "call_id": "call_abc",
                "output": json.dumps(tool_result)
            }
        ],
        reasoning={"effort": "high"},
        tools=tools,
    )
    print("\nROUND 2 CAPTURED:")
    print(json.dumps(captured[1]["body"], indent=2))
    print("ROUND 2 OUTPUT:", res2.output)

if __name__ == "__main__":
    asyncio.run(main())
