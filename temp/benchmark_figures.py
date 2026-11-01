import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import fitz
from ingestion.pipeline_worker import (
    _build_sections_from_toc,
    _crop_figure_from_page,
    _generate_chunks_from_sections,
)

pdf_path = Path("Harrison 2025 _ 22nd Edition.pdf")
doc = fitz.open(str(pdf_path))

# Check pages 50 to 150 (dense clinical section)
pages_data = []
t0 = time.perf_counter()
for pno in range(50, 150):
    page = doc[pno]
    blocks = page.get_text("blocks")
    page_height = page.rect.height
    filtered = [b[4].strip() for b in blocks if len(b) >= 5 and 35 <= b[1] and b[3] <= page_height - 35 and b[4].strip()]
    pages_data.append({"page_num": pno + 1, "text": "\n\n".join(filtered)})

sections = [
    {
        "id": 1,
        "title": "Clinical Section Sample",
        "level": 1,
        "parent_id": None,
        "pdf_start": 51,
        "pdf_end": 150,
        "heading_path": "Part 1 > Sample",
        "is_leaf": True,
    }
]

t1 = time.perf_counter()
chunks = _generate_chunks_from_sections("harrison_test", sections, pages_data, target_tokens=400, doc=doc)
t2 = time.perf_counter()

fig_chunks = [c for c in chunks if c["content_type"] == "figure_caption"]
print(f"Generated {len(chunks)} chunks in {t2 - t1:.2f}s")
print(f"Figure caption chunks: {len(fig_chunks)}")

doc.close()
