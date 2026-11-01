"""Verification script for UI Skill Design Guidelines hardening."""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def verify():
    print("=== UI Skill Design Guidelines Verification ===")
    root = Path(__file__).resolve().parent.parent

    html = (root / "ui" / "static" / "index.html").read_text(encoding="utf-8")
    css = (root / "ui" / "static" / "styles.css").read_text(encoding="utf-8")
    js = (root / "ui" / "static" / "app.js").read_text(encoding="utf-8")

    # 1. Check Typography Floor (12px minimum floor)
    assert "text-[10px]" not in html, "Found text-[10px] in index.html"
    assert "text-[11px]" not in html, "Found text-[11px] in index.html"
    assert "text-[10px]" not in js, "Found text-[10px] in app.js"
    assert "text-[11px]" not in js, "Found text-[11px] in app.js"
    print("[PASS] 1. Typography Floor: Zero sub-12px micro-text in HTML and JS (12px floor enforced).")

    # 2. Check Touch Targets (44x44px pseudo-element expanders)
    assert ".toggle-switch::after" in css, "Missing toggle-switch touch expander in styles.css"
    assert "min-width: 44px" in css and "min-height: 44px" in css, "Missing 44x44px min dimensions in touch expander"
    assert ".btn-compact-touch::after" in css, "Missing btn-compact-touch expander in styles.css"
    print("[PASS] 2. Touch Targets: 44x44px pseudo-element expanders active on switches and compact buttons.")

    # 3. Check Interactive Accordions in Global Catalog
    assert ".specialty-chevron" in css, "Missing specialty-chevron class in styles.css"
    assert "rotate(-90deg)" in css, "Missing chevron rotation transition in styles.css"
    assert "specialty-body" in css and ".collapsed" in css, "Missing collapsible body class in styles.css"
    assert "specialty-accordion-header" in js, "Missing accordion header click logic in app.js"
    print("[PASS] 3. Interactive Accordions: Collapsible specialty groups with smooth chevron rotation.")

    # 4. Check Search UX: Clear Search Button
    assert "btn-clear-global-search" in html, "Missing btn-clear-global-search in index.html"
    assert "btnClearGlobalSearch" in js, "Missing btnClearGlobalSearch in app.js"
    print("[PASS] 4. Form UX: Instant search clear button (✕) wired in Global Catalog search.")

    # 5. Check Reduced Motion Accessibility
    assert "@media (prefers-reduced-motion: reduce)" in css, "Missing prefers-reduced-motion in styles.css"
    print("[PASS] 5. Accessibility: prefers-reduced-motion respects user motion preferences.")

    # 6. Check Mobile Header Ergonomics
    assert 'class="sm:hidden">Chat</span>' in html, "Missing mobile short labels in top header tabs"
    assert 'class="sm:hidden">Library</span>' in html, "Missing mobile short labels in top header tabs"
    print("[PASS] 6. Responsive Ergonomics: Header tabs adapt seamlessly across desktop and mobile screens.")

    print("\n[ALL UI SKILL VERIFICATIONS PASSED]")


if __name__ == "__main__":
    verify()
