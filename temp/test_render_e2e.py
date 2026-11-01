import httpx

RENDER_URL = "https://text-book-rag-etiz.onrender.com"

with httpx.Client(base_url=RENDER_URL, timeout=30.0) as client:
    # 1. Check guest auth
    r_auth = client.post("/api/auth/guest")
    print(f"POST /api/auth/guest -> {r_auth.status_code}")
    print(f"Auth Response: {r_auth.text}")
    
    # 2. Check user library (Phase 3 endpoint)
    r_lib = client.get("/api/user/library")
    print(f"GET /api/user/library -> {r_lib.status_code}")
    if r_lib.status_code == 200:
        data = r_lib.json()
        print("Phase 3 User Library endpoint is ACTIVE!")
        print(f"Library count: {len(data.get('library', []))}")
        print(f"Global catalog count: {len(data.get('global_catalog', []))}")
    else:
        print(f"Response: {r_lib.text}")
