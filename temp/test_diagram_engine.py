import re, sys
sys.stdout.reconfigure(encoding='utf-8')
import pymupdf
from pathlib import Path

ROOT = Path.cwd()
BOOKS_DIR = ROOT / "ingestion" / "test-books"
CACHE_DIR = ROOT / "temp" / "test_cache"

pdf_path = BOOKS_DIR / "Williams Textbook of Endocrinology, 15th edition 2.pdf"
doc = pymupdf.open(str(pdf_path))
page = doc[800] # 0-based 800 is 1-based 801

for token in ["Fig. 16.3", "Fig. 16.4"]:
    print(f"\nSearching for caption of {token}...")
    caption_block = None
    pattern = re.compile(r"^\s*(?:[•·\-\*]\s*)?" + re.escape(token), re.IGNORECASE | re.MULTILINE)
    for b in page.get_text("blocks"):
        if pattern.search(b[4]):
            caption_block = b
            print(f"Matched Caption Block: {b[:4]} -> {b[4].strip()[:80]}")
            break
            
    if caption_block:
        cap_rect = pymupdf.Rect(caption_block[:4])
        matched_img_rect = None
        for img in page.get_images():
            xref = img[0]
            for img_r in page.get_image_rects(xref):
                # Image must be above caption and horizontally aligned
                if img_r.y1 <= cap_rect.y0 + 20 and img_r.y1 >= cap_rect.y0 - 450:
                    # Check horizontal alignment
                    if max(img_r.x0, cap_rect.x0) < min(img_r.x1, cap_rect.x1) or abs(img_r.x0 - cap_rect.x0) < 60:
                        matched_img_rect = img_r
                        break
            if matched_img_rect:
                break
                
        print(f"Matched Image: {matched_img_rect}")
        if matched_img_rect:
            x0 = max(0, min(matched_img_rect.x0, cap_rect.x0) - 8)
            x1 = min(page.rect.x1, max(matched_img_rect.x1, cap_rect.x1) + 8)
            y0 = max(0, matched_img_rect.y0 - 8)
            y1 = min(page.rect.y1, cap_rect.y1 + 8)
            crop_rect = pymupdf.Rect(x0, y0, x1, y1)
        else:
            y0 = max(0, cap_rect.y0 - 350)
            y1 = min(page.rect.y1, cap_rect.y1 + 10)
            crop_rect = pymupdf.Rect(page.rect.x0, y0, page.rect.x1, y1)
            
        pix = page.get_pixmap(clip=crop_rect, dpi=130)
        out = CACHE_DIR / f"{token.replace(' ', '_').replace('.', '_')}.jpg"
        pix.save(str(out))
        print(f"Saved: {out.name} ({pix.width}x{pix.height}) crop: {crop_rect}")
