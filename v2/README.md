# 🌱 Regrow — Circular Economy OS

> **WhatsApp → API → Database → AI Grading → Dashboard**  
> A working MVP for waste textile collection, AI grading, and ESG tracking.

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      REGROW MVP STACK                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📱 WhatsApp               🌐 Dashboard                         │
│  (User interface)          (Next.js + Tailwind)                  │
│       │                         │                               │
│       ▼                         ▼                               │
│  ┌─────────────────────────────────────────┐                    │
│  │  FastAPI Backend (Python)               │                    │
│  │  /api/webhook/whatsapp                  │                    │
│  │  /api/pickups                           │                    │
│  │  /api/files/upload                      │                    │
│  │  /api/auth                              │                    │
│  └─────────────────┬───────────────────────┘                    │
│                    │                                            │
│       ┌────────────┼────────────┐                              │
│       ▼            ▼            ▼                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│  │PostgreSQL│  │  Redis  │  │  MinIO  │                        │
│  │(Database)│  │ (Queue) │  │(Storage)│                        │
│  └─────────┘  └────┬────┘  └─────────┘                        │
│                    │                                            │
│               ┌────▼────────────┐                              │
│               │  RQ Worker      │                              │
│               │  (Grading)      │                              │
│               │  Gemini Vision  │                              │
│               └─────────────────┘                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
regrow/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py         # Login / register operator
│   │   │   ├── pickups.py      # CRUD for pickups
│   │   │   ├── files.py        # File upload + job status
│   │   │   ├── webhook.py      # WhatsApp webhook router
│   │   │   └── users.py        # User info
│   │   ├── core/
│   │   │   ├── config.py       # Pydantic settings
│   │   │   ├── database.py     # Async SQLAlchemy engine
│   │   │   └── security.py     # JWT auth
│   │   ├── models/
│   │   │   ├── models.py       # SQLAlchemy ORM models
│   │   │   └── schemas.py      # Pydantic schemas
│   │   ├── services/
│   │   │   ├── storage.py      # MinIO operations
│   │   │   ├── queue.py        # RQ job queue
│   │   │   └── whatsapp.py     # WA API + intent parser
│   │   ├── workers/
│   │   │   └── classification_worker.py  # Gemini Vision grading
│   │   └── main.py             # FastAPI app
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── login/page.tsx       # Login form
│   │   │   ├── pickups/page.tsx     # Pickup list
│   │   │   └── pickups/[id]/page.tsx # Pickup detail + grade
│   │   ├── components/
│   │   │   ├── Sidebar.tsx
│   │   │   └── StatusBadge.tsx
│   │   └── lib/
│   │       └── api.ts               # Axios client
│   ├── Dockerfile
│   ├── next.config.js
│   └── package.json
│
├── scripts/
│   ├── setup.sh          # One-command setup
│   └── test_pipeline.sh  # End-to-end test
│
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Docker + Docker Compose
- (Optional) Gemini API key for real AI grading
- (Optional) WhatsApp Business API credentials

### 1. Clone and setup

```bash
# Copy project
cd regrow

# Run one-command setup
chmod +x scripts/setup.sh
./scripts/setup.sh
```

That's it! The script will:
1. Create `.env` from `.env.example`
2. Build all Docker images
3. Start all 6 services
4. Create default operator account
5. Print access URLs

### 2. Access services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dashboard** | http://localhost:3000 | Phone: `08001234567` / PW: `regrow123` |
| **API Docs** | http://localhost:8001/docs | — |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin` |
| **PostgreSQL** | localhost:5432 | `regrow` / `regrowpass` |

### 3. Test the pipeline

```bash
chmod +x scripts/test_pipeline.sh
./scripts/test_pipeline.sh
```

---

## 🔧 Configuration

Edit `.env` before starting:

```env
# Required for real AI grading:
GEMINI_API_KEY=your-key-from-aistudio.google.com

# Required for WhatsApp integration:
WHATSAPP_API_TOKEN=your-meta-api-token
WHATSAPP_PHONE_ID=your-phone-number-id
WHATSAPP_VERIFY_TOKEN=regrow-verify-token  # Your custom verify token
```

**Get Gemini API key:** https://aistudio.google.com/app/apikey (free)

---

## 📱 WhatsApp Flow

### Setup
1. Create a Meta App at https://developers.facebook.com
2. Add WhatsApp Business product
3. Configure webhook URL: `https://your-domain/api/webhook/whatsapp`
4. Verify token: `regrow-verify-token`
5. Subscribe to `messages` events

### Conversation Flow

```
User:   "Saya mau jemput sampah"
Bot:    "Apa jenis sampah yang akan dijemput?"

User:   "Baju bekas dan celana"
Bot:    "Kirimkan alamat lengkap untuk penjemputan:"

User:   "Jl. Kebon Jeruk No. 5, Jakarta Barat"
Bot:    "🎉 Booking berhasil! ID: ABCD1234
         Jenis: Baju bekas dan celana
         Lokasi: Jl. Kebon Jeruk No. 5..."

User:   "status"
Bot:    "📋 Status Pickup ABCD1234
         ⏳ Status: PENDING
         ..."
```

### Testing Locally (without Meta approval)
```bash
# Simulate incoming WhatsApp message
curl -X POST http://localhost:8001/api/webhook/whatsapp \
  -H "Content-Type: application/json" \
  -d '{
    "entry": [{
      "changes": [{
        "value": {
          "messages": [{
            "from": "628123456789",
            "type": "text",
            "text": {"body": "jemput"}
          }]
        }
      }]
    }]
  }'
```

---

## 🔌 API Reference

### Auth
```
POST /api/auth/login              Login operator
POST /api/auth/register-operator  Create operator account
```

### Pickups
```
POST   /api/pickups               Create pickup
GET    /api/pickups               List all (paginated, filterable)
GET    /api/pickups/{id}          Get pickup + files + grade
PATCH  /api/pickups/{id}          Update status
```

### Files
```
POST /api/files/upload?pickup_id={id}   Upload photo → enqueue grading
GET  /api/files/{file_id}/url            Get presigned URL
GET  /api/files/job/{job_id}             Poll grading job status
```

### Webhook
```
GET  /api/webhook/whatsapp    Webhook verification (Meta)
POST /api/webhook/whatsapp    Receive messages
```

---

## 🤖 AI Grading

The grading pipeline:

```
1. File uploaded → stored in MinIO
2. Job enqueued in Redis (grading_queue)
3. RQ worker picks up job
4. Downloads image from MinIO
5. Sends to Gemini Vision API
6. Parses JSON response:
   {
     "grade": "A",          # A/B/C/D
     "confidence": 0.85,    # 0.0-1.0
     "reasoning": "...",    # In Indonesian
     "estimated_kg": 2.5
   }
7. Saves to PostgreSQL (grades table)
8. Updates pickup.status = "graded"
9. Sends WhatsApp notification to user
```

**Without Gemini key:** Worker uses deterministic mock grades for development.

---

## 🐳 Docker Services

| Container | Image | Purpose | Port |
|-----------|-------|---------|------|
| `regrow_postgres` | postgres:16 | Primary database | 5432 |
| `regrow_redis` | redis:7 | Job queue + cache | 6379 |
| `regrow_minio` | minio/minio | Object storage | 9000/9001 |
| `regrow_backend` | Custom FastAPI | REST API | 8001 |
| `regrow_worker` | Custom RQ | Grading worker | — |
| `regrow_frontend` | Custom Next.js | Dashboard | 3000 |

### Useful commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f frontend

# Restart single service
docker compose restart backend

# Access PostgreSQL
docker exec -it regrow_postgres psql -U regrow -d regrow_db

# Access Redis
docker exec -it regrow_redis redis-cli

# Stop everything
docker compose down

# Stop and delete data
docker compose down -v
```

---

## 📊 Database Schema

```sql
-- users
id UUID PRIMARY KEY
phone VARCHAR(20) UNIQUE NOT NULL
name VARCHAR(100)
role ENUM(user, operator, admin)
password_hash VARCHAR(255)
created_at TIMESTAMP

-- pickups
id UUID PRIMARY KEY
user_id UUID → users.id
location TEXT NOT NULL
waste_type VARCHAR(100) NOT NULL
estimated_weight FLOAT
status ENUM(pending, confirmed, grading, graded, completed, cancelled)
notes TEXT
created_at TIMESTAMP
updated_at TIMESTAMP

-- files
id UUID PRIMARY KEY
pickup_id UUID → pickups.id
file_path VARCHAR(500)   -- MinIO object key
file_name VARCHAR(255)
mime_type VARCHAR(100)
size_bytes FLOAT
created_at TIMESTAMP

-- grades
id UUID PRIMARY KEY
file_id UUID → files.id (UNIQUE)
grade ENUM(A, B, C, D)
confidence FLOAT
reasoning TEXT
estimated_kg FLOAT
graded_by VARCHAR(50)
created_at TIMESTAMP
```

---

## 🛣️ Roadmap

### MVP (Shipped) ✅
- WhatsApp booking flow (3-step conversation)
- File upload + MinIO storage
- Gemini AI grading (async via RQ)
- Operator dashboard (list + detail)
- JWT auth for operators
- Docker Compose 6-service setup

### Phase 2 (Next 4 weeks)
- [ ] ESG impact metrics dashboard
- [ ] Payout tracking (Stripe or manual)
- [ ] Operator mobile view (PWA)
- [ ] Bulk pickup scheduling
- [ ] WhatsApp photo upload flow

### Phase 3 (8-12 weeks)
- [ ] Marketplace (buyer/seller)
- [ ] B2B corporate partner workspace
- [ ] Analytics dashboard
- [ ] Event-sourced audit trail
- [ ] SIPSN compliance export

---

## 🤝 Contributing

1. Fork the repo
2. Create feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -m 'feat: add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

---

*Built for Indonesia 🇮🇩 — Circular Economy for Textile Waste*
