"""Verification script for Semantic Book Routing and Explicit UI Attribution."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from ui.app import app


async def verify():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        await client.get("/api/auth/me")
        cases = [
            ("All Books Endo", "What are the layers of the adrenal cortex and their hormones?", None),
            ("All Books Anatomy", "What are the boundaries and contents of the femoral triangle?", None),
            ("User Explicit Lock", "Explain thyroid hormone synthesis", ["anatomy-and-physiology-2e_-_WEB"]),
        ]
        for label, query, books in cases:
            print(f"\n==========================================")
            print(f"CASE: {label}")
            print(f"Query: '{query}'")
            print(f"Explicit Books: {books}")
            print(f"==========================================")
            sid = f"verify_{label.lower().replace(' ', '_')}"
            payload = {"session_id": sid, "message": query}
            if books:
                payload["active_books"] = books

            async with client.stream("POST", "/api/chat/stream", json=payload, timeout=40.0) as resp:
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        lines = [l.strip() for l in block.split("\n") if l.strip()]
                        evt = "message"
                        data = ""
                        for line in lines:
                            if line.startswith("event:"):
                                evt = line.split(":", 1)[1].strip()
                            elif line.startswith("data:"):
                                data = line.split(":", 1)[1].strip()

                        if evt == "referenced_books":
                            print(f"[SSE Event] event: referenced_books")
                            try:
                                parsed = json.loads(data)
                                print(f"  Referenced Books Data: {json.dumps(parsed, indent=2)}")
                            except Exception:
                                print(f"  Raw: {data}")
                        elif evt == "plan":
                            print(f"[SSE Event] event: plan emitted")


if __name__ == "__main__":
    asyncio.run(verify())
