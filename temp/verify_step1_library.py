"""Verification script for Step 1: Dedicated Library Page & Dual-Scroll Sidebar."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from ui.app import app


async def verify():
    print("=== Step 1 Human & Automated Verification ===")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Verify HTML template
        res_html = await client.get("/")
        assert res_html.status_code == 200, f"Root returned {res_html.status_code}"
        html = res_html.text
        for tag in [
            "tab-view-consultation",
            "tab-view-library",
            "sidebar-sessions-container",
            "sidebar-library-container",
            "sidebar-book-count-badge",
            "view-consultation",
            "view-library",
            "subpanel-my-library",
            "subpanel-global-catalog",
            "global-catalog-search",
        ]:
            assert tag in html, f"Missing element tag '{tag}' in HTML"
        print("[PASS] 1. HTML serves top navigation tabs, dual-scroll sidebar, and dedicated library page.")

        # 2. Verify User Library API
        res_lib = await client.get("/api/user/library")
        assert res_lib.status_code == 200, f"Library API failed: {res_lib.status_code}"
        lib_data = res_lib.json()
        print(f"[PASS] 2. User Library returned {len(lib_data['library'])} books (Active: {lib_data['total_active']}).")
        assert lib_data["total_active"] >= 2

        # 3. Verify Active Scope Toggle
        first_slug = lib_data["library"][0]["slug"]
        res_toggle = await client.post("/api/user/library/toggle", json={"slug": first_slug, "is_active": False})
        assert res_toggle.status_code == 200
        print(f"[PASS] 3. Toggled book '{first_slug}' to inactive. Total active now: {res_toggle.json()['total_active']}.")

        # 4. Verify Remove from Library
        res_remove = await client.post("/api/user/library/remove", json={"slug": first_slug})
        assert res_remove.status_code == 200
        print(f"[PASS] 4. Removed book '{first_slug}' from user library.")

        # 5. Verify Add back from Global Catalog
        res_add = await client.post("/api/user/library/add", json={"slug": first_slug})
        assert res_add.status_code == 200
        print(f"[PASS] 5. Added book '{first_slug}' back to user library.")

        # 6. Verify Toggle All
        res_all = await client.post("/api/user/library/toggle-all", json={"active": True})
        assert res_all.status_code == 200
        assert res_all.json()["total_active"] == len(res_all.json()["library"])
        print(f"[PASS] 6. Reactivated all books. Total active: {res_all.json()['total_active']}.")

    print("\n[ALL STEP 1 VERIFICATIONS PASSED]")


if __name__ == "__main__":
    asyncio.run(verify())
