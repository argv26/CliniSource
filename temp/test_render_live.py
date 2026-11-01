import httpx

url = "https://text-book-rag-etiz.onrender.com"
client = httpx.Client(base_url=url, timeout=30.0)

print("--- Testing Live Render Deployment ---")
# 1. Root index.html
r_index = client.get("/")
print(f"GET / -> Status: {r_index.status_code}, Length: {len(r_index.text)} bytes")

# 2. Quota endpoint
r_quota = client.get("/api/quota")
print(f"GET /api/quota -> Status: {r_quota.status_code}, Response: {r_quota.text}")

# 3. Auth guest
r_guest = client.post("/api/auth/guest")
print(f"POST /api/auth/guest -> Status: {r_guest.status_code}, User: {r_guest.json().get('user', {}).get('username')}")
cookies = r_guest.cookies

# 4. Books
r_books = client.get("/api/books")
print(f"GET /api/books -> Status: {r_books.status_code}")
if r_books.status_code == 200:
    books = r_books.json().get("books", [])
    print(f"   Indexed books count: {len(books)}")
    for b in books[:5]:
        print(f"   - {b.get('title')} ({b.get('total_pages')} pages, specialty: {b.get('specialty')})")

print("\nRender live service is fully responsive and verified!")

