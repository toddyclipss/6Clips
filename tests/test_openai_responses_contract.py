import asyncio
import json
import httpx
import openai

async def main():
    events_to_stream = [
        'event: response.output_item.added\ndata: {"type": "response.output_item.added", "item": {"type": "message", "role": "assistant"}}\n\n',
        'event: response.output_text.delta\ndata: {"type": "response.output_text.delta", "delta": "Hello "}\n\n',
        'event: response.output_text.delta\ndata: {"type": "response.output_text.delta", "delta": "world!"}\n\n',
        'event: response.completed\ndata: {"type": "response.completed"}\n\n'
    ]
    sse_content = ''.join(events_to_stream).encode('utf-8')

    captured = {}
    def handler(request: httpx.Request):
        captured['url'] = str(request.url)
        captured['method'] = request.method
        captured['body'] = json.loads(request.content.decode('utf-8'))
        return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, content=sse_content)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = openai.AsyncOpenAI(api_key='sk-test', http_client=http_client)

    stream = await client.responses.create(
        model='gpt-6-astra',
        input=[{'role': 'user', 'content': 'Hi'}],
        reasoning={'effort': 'high'},
        stream=True
    )
    tokens = []
    async for event in stream:
        if getattr(event, 'type', None) == 'response.output_text.delta':
            tokens.append(event.delta)

    print('CAPTURED URL:', captured['url'])
    print('CAPTURED BODY:', json.dumps(captured['body'], indent=2))
    print('STREAMED TOKENS:', tokens)

if __name__ == '__main__':
    asyncio.run(main())
