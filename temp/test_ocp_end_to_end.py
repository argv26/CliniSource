import sys
from pathlib import Path
sys.path.insert(0, ".")
from starlette.testclient import TestClient
from ui.app import app
import pymupdf

client = TestClient(app)

print("=" * 60)
print("TESTING OCP CONTRAINDICATIONS & FIGURE 16.2 RETRIEVAL")
print("=" * 60)

# 1. Parallel retrieval test for "contraindications of OCP"
from retrieval.parallel import execute_parallel_retrieval
res = execute_parallel_retrieval("contraindications of OCP", figure_limit=2)

print(f"Clean query: {res['clean_query']}")
print(f"Chunks retrieved: {len(res['chunks'])}")
print(f"Sections retrieved: {len(res['sections'])}")
print(f"Figures retrieved: {len(res['figures'])}")

williams_fig = None
for f in res["figures"]:
    print(f"  Figure Chunk: {f['chunk_id']}")
    print(f"  Book: {f['book_slug']} | Page: {f.get('page_start')}")
    print(f"  Caption: {f['text'][:80].replace(chr(10), ' ')}")
    if "s1165_c004" in f["chunk_id"]:
        williams_fig = f

assert len(res["figures"]) > 0, "Expected at least 1 verified figure"
assert williams_fig is not None, "Williams Fig 16.2 (s1165_c004) should be among verified figures"
print("\n PASS: Verified Fig 16.2 is retrieved and authenticated!")

# 2. Check the image endpoint for Fig 16.2
cid = williams_fig["chunk_id"]
resp = client.get(f"/api/figure/{cid}/image")
assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}"
assert resp.headers.get("content-type") == "image/jpeg"
assert len(resp.content) >= 5000, f"Image too small: {len(resp.content)} bytes"

# 3. Check image dimensions: MUST BE isolated column crop (approx 704x707 px), NEVER full page (1020x1305)
pix = pymupdf.Pixmap(resp.content)
print(f"\nFigure Image Served:")
print(f"  Width: {pix.width} px")
print(f"  Height: {pix.height} px")
print(f"  Size: {len(resp.content):,} bytes")

assert (pix.width, pix.height) != (1020, 1305), "CRITICAL FAILURE: Full page of text served instead of cropped diagram!"
assert 600 <= pix.width <= 800, f"Expected width around 704 px, got {pix.width}"
assert 600 <= pix.height <= 800, f"Expected height around 707 px, got {pix.height}"

print("\n PASS: Figure 16.2 is cleanly cropped to the VTE bar chart without right-column text!")
print("=" * 60)
