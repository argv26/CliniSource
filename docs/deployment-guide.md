# CliniSource: Production Deployment Guide

This guide details how to deploy the **CliniSource** platform across containerized environments, cloud providers, and dedicated Linux servers.

---

## 1. Quick Local Docker Deployment

The application is completely self-contained. The pre-indexed reference SQLite database (containing over 34,000 indexed chunks across 9,200+ pages of clinical reference canon including Harrison's 22e, Williams 15e, and Cornea 5e) is packaged directly into the container image, requiring zero external database configuration.

### Step-by-Step:
1. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Set GEMINI_API_KEY (optional: application operates fully offline with local synthesizer)
   ```

2. **Build and Run:**
   ```bash
   docker compose up --build -d web
   ```

3. **Verify:**
   Open your browser at `http://localhost:8000`.

---

## 2. Deploying to Google Cloud Run (Serverless)

Google Cloud Run provides automatic scaling, HTTPS, and zero costs when idle.

### Deployment Commands:
```bash
# 1. Authenticate with Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Build and push container to Google Artifact Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/clinisource

# 3. Deploy to Cloud Run
gcloud run deploy clinisource \
  --image gcr.io/YOUR_PROJECT_ID/clinisource \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi \
  --set-env-vars "DAILY_REQUEST_LIMIT=50,GEMINI_API_KEY=YOUR_KEY"
```

---

## 3. Deploying to Render / Railway

### Live Production Deployment on Render:
- **Live URL**: [`https://text-book-rag-etiz.onrender.com`](https://text-book-rag-etiz.onrender.com)
- **Health Check Endpoint**: `https://text-book-rag-etiz.onrender.com/api/quota`

### Steps for Render Deployment:
1. Connect your GitHub repository (`https://github.com/argv26/CliniSource`) to [Render.com](https://render.com).
2. Choose **Web Service** with the **Docker** runtime.
3. In the **Environment Variables** section, configure:
   - `PORT`: `8000`
   - `DAILY_REQUEST_LIMIT`: `50`
   - `GEMINI_API_KEY`: `your-gemini-key`
4. Click **Deploy**. Render builds the `Dockerfile` and provisions an automatic SSL-secured `https://` domain.

### Railway Deployment:
1. Open [Railway.app](https://railway.app) and select **Deploy from GitHub repo**.
2. Railway detects the `Dockerfile` automatically.
3. Add environment variables in the Railway dashboard (`GEMINI_API_KEY`, `DAILY_REQUEST_LIMIT`).
4. Generate a public domain under service settings.

---

## 4. Deploying to Dedicated Linux Server (Ubuntu / Debian)

### Using Docker Compose:
```bash
git clone https://github.com/argv26/CliniSource.git
cd CliniSource
cp .env.example .env
# Edit .env with your credentials
docker compose up -d web
```

### Using Systemd (Native Python):
```bash
# 1. Install Python 3.11 and create virtual environment
sudo apt update && sudo apt install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Create systemd service (/etc/systemd/system/clinisource.service)
[Unit]
Description=CliniSource Knowledge Platform
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/CliniSource
EnvironmentFile=/home/ubuntu/CliniSource/.env
ExecStart=/home/ubuntu/CliniSource/.venv/bin/uvicorn ui.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target

# 3. Reload daemon and start
sudo systemctl daemon-reload
sudo systemctl enable --now clinisource
```

---

## 5. Production Environment Variables Reference

| Environment Variable | Recommended Value | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | *(Secret key)* | Enables high-speed Google Gemini 2.0 Flash tool-calling ReAct engine |
| `OPENAI_API_KEY` | *(Secret key)* | Optional alternative LLM provider |
| `DAILY_REQUEST_LIMIT` | `50` | Maximum queries per user/IP daily quota (set `0` to disable quota) |
| `PORT` | `8000` | Port for the HTTP web server |
| `DATABASE_URL` | *(Omit for SQLite)* | Optional PostgreSQL connection string for distributed multi-node clusters |
| `STORAGE_PROVIDER` | `local` | Storage driver (`local` or `s3`) for figure caching |
