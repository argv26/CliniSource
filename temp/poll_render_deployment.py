import time
import httpx

RENDER_URL = "https://text-book-rag-etiz.onrender.com"
max_attempts = 20
delay = 15

print("Waiting for Render to finish building and deploying commit dc871e7...")
for attempt in range(1, max_attempts + 1):
    try:
        with httpx.Client(base_url=RENDER_URL, timeout=15.0) as client:
            client.post("/api/auth/guest")
            r = client.get("/api/user/library")
            if r.status_code == 200:
                print(f"\n[SUCCESS] Render is now running the new Phase 3 deployment! (Attempt {attempt})")
                print("Response data:", r.json())
                exit(0)
            else:
                print(f"[{attempt}/{max_attempts}] Deployment still building... (/api/user/library returned {r.status_code})")
    except Exception as e:
        print(f"[{attempt}/{max_attempts}] Connecting to Render... ({e})")
    time.sleep(delay)

print("\nTimed out waiting for deployment to go live.")
exit(1)

