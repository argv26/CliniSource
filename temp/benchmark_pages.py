import time
import fitz
from pathlib import Path

pdf_path = Path("Harrison 2025 _ 22nd Edition.pdf")
doc = fitz.open(str(pdf_path))

sample_count = 100
t0 = time.perf_counter()
for i in range(sample_count):
    page = doc[i]
    blocks = page.get_text("blocks")
elapsed = time.perf_counter() - t0

pages_per_sec = sample_count / elapsed
total_est_seconds = len(doc) / pages_per_sec

print(f"Sampled {sample_count} pages in {elapsed:.2f}s ({pages_per_sec:.1f} pages/sec)")
print(f"Estimated time for all {len(doc)} pages: {total_est_seconds:.1f}s ({total_est_seconds / 60:.1f} minutes)")

doc.close()

