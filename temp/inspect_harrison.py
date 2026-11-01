import fitz
from pathlib import Path

pdf_path = Path("Harrison 2025 _ 22nd Edition.pdf")
print(f"File exists: {pdf_path.exists()}")
print(f"File size: {pdf_path.stat().st_size / (1024 * 1024):.2f} MB")

doc = fitz.open(str(pdf_path))
print(f"Total pages: {len(doc)}")
print(f"Is encrypted: {doc.is_encrypted}")

toc = doc.get_toc()
print(f"TOC entries found: {len(toc)}")
if toc:
    print("Sample TOC entries (first 10):")
    for item in toc[:10]:
        print("  ", item)
else:
    print("No native PDF TOC outline found.")

# Sample text from first few non-blank pages
for pno in [0, 5, 20, 50, 100]:
    if pno < len(doc):
        page = doc[pno]
        text = page.get_text()
        print(f"\n--- Page {pno + 1} (Text length: {len(text)}) ---")
        preview = text.strip()[:200].replace("\n", " ")
        print(f"Preview: {preview}")

doc.close()

