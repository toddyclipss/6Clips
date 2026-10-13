import asyncio
import json
from uuid import uuid4
from datetime import datetime
from backend.database import AsyncSessionLocal
from backend.models.chat_session import ChatSession, ChatMessage

async def main():
    async with AsyncSessionLocal() as db:
        session_id = f"demo-timeline-{uuid4().hex[:8]}"
        session = ChatSession(
            id=session_id,
            user_id="local",
            title="Main Agent Tool Execution Demo",
            message_count=2,
        )
        db.add(session)

        user_msg = ChatMessage(
            session_id=session_id,
            user_id="local",
            role="user",
            content="Search the motion graphics catalog for titles and insert the first one into my project.",
        )
        db.add(user_msg)

        timeline = [
            {
                "id": "step_1_catalog",
                "title": "Execute search_catalog",
                "status": "completed",
                "duration_ms": 245,
                "tool_calls": [
                    {
                        "id": "tc_cat_01",
                        "name": "search_catalog",
                        "state": "output-available",
                        "arguments": {
                            "query": "title",
                            "category": "titles",
                            "limit": 5
                        },
                        "result": {
                            "status": "success",
                            "count": 2,
                            "items": [
                                {
                                    "id": "canopy-part-title",
                                    "title": "Canopy Part Title",
                                    "category": "titles",
                                    "description": "High-impact kinetic title sequence"
                                },
                                {
                                    "id": "carousel-text-circle-1",
                                    "title": "Carousel Text Circle",
                                    "category": "titles",
                                    "description": "Circular rotating text badge"
                                }
                            ]
                        },
                        "duration_ms": 245
                    }
                ]
            },
            {
                "id": "step_2_project_op",
                "title": "Execute project_operation",
                "status": "failed",
                "duration_ms": 95,
                "tool_calls": [
                    {
                        "id": "tc_proj_02",
                        "name": "project_operation",
                        "state": "output-error",
                        "arguments": {
                            "project_id": "proj_current",
                            "operation_type": "insert_block",
                            "expected_revision": 2,
                            "payload": {
                                "block_id": "canopy-part-title"
                            }
                        },
                        "result": {
                            "status": "error",
                            "error": "CAS conflict: expected_revision 2 does not match authoritative revision 3"
                        },
                        "error": "CAS conflict: expected_revision 2 does not match authoritative revision 3",
                        "duration_ms": 95
                    }
                ]
            }
        ]

        assistant_content = (
            "I searched the catalog and found 2 matching titles:\n\n"
            "- **Canopy Part Title** (`canopy-part-title`)\n"
            "- **Carousel Text Circle** (`carousel-text-circle-1`)\n\n"
            "Attempting to insert `canopy-part-title` encountered a revision conflict because the project had been updated in another tab."
        )

        assistant_msg = ChatMessage(
            session_id=session_id,
            user_id="local",
            role="assistant",
            content=assistant_content,
            data_json=json.dumps({"execution_timeline": timeline}),
        )
        db.add(assistant_msg)

        await db.commit()
        print("Created demo session:", session_id)

if __name__ == "__main__":
    asyncio.run(main())
