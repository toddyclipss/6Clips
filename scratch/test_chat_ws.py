import asyncio
import json
import websockets

async def test_chat():
    uri = "ws://127.0.0.1:16889/ws/chat"
    
    async with websockets.connect(uri, origin="http://127.0.0.1:16889") as ws:
        print("Connected to WebSocket.")
        
        # Send chat_message with explicit provider, model, reasoning_level
        payload = {
            "type": "chat_message",
            "content": "Create a 30-second 9:16 gaming highlight from my gameplay. Pick the best moment, add synchronized captions and an animated intro, and show me the finished video.",
            "provider": "ollama",
            "model": "gemma4:e4b",
            "reasoning_level": "low",
            "project_id": "6169c61a-9805-43fa-9230-7806f4ed922b"
        }
        await ws.send(json.dumps(payload))
        print("Sent chat message. Waiting for stream response...")
        
        # Read stream responses
        events = []
        full_text = []
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=40.0)
                data = json.loads(msg)
                mtype = data.get("type")
                events.append(mtype)
                
                if mtype in ("thought_start", "thought_delta", "thought_end", "tool_call", "tool_result", "session_created", "chat_error"):
                    print(f"\n[EVENT] {mtype} -> {json.dumps(data)[:200]}")
                elif mtype == "chat_stream":
                    chunk = data.get("chunk", "")
                    full_text.append(chunk)
                    print(chunk, end="", flush=True)
                elif mtype == "chat_done":
                    print(f"\n\n[SUCCESS] CHAT_DONE received! Total events: {len(events)}")
                    break
            except asyncio.TimeoutError:
                print("\nTimeout waiting for more events.")
                break

if __name__ == "__main__":
    asyncio.run(test_chat())
