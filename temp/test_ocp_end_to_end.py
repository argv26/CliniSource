import sys
import os
import json
sys.path.insert(0, os.path.abspath("."))

from agent.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
stream = orchestrator.stream_turn(
    session_id="test-ocp-session",
    user_message="contraindications of OCP",
    active_books=None
)

collected = []
figures = []
citations = []
tools = []

for item in stream:
    event_type = item.get("event")
    data = item.get("data")
    if event_type == "token":
        collected.append(data.get("delta", ""))
    elif event_type == "figures":
        figures = data
    elif event_type == "citations":
        citations = data
    elif event_type == "tools":
        tools = data

full_response = "".join(collected)
print(f"--- TOOLS CALLED ({len(tools)}) ---")
for t in tools:
    print(t)

print(f"\n--- FIGURES EMITTED ({len(figures)}) ---")
for f in figures:
    print(f"Fig: {f.get('chunk_id')} | Page: {f.get('page_start')} | Text: {f.get('text')[:100]}")

print(f"\n--- CITATIONS ({len(citations)}) ---")
for c in citations:
    print(f"[{c.get('citation_id')}] Chunk: {c.get('chunk_id')} | Book: {c.get('book_slug')}")

print(f"\n--- RESPONSE PREVIEW (First 500 chars) ---")
print(full_response[:500])
