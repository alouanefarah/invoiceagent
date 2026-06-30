# InvoiceAgent — : Pipeline OCR

## Prérequis
- Docker + Docker Compose
- Python 3.12 (pour migrations en local)
- Clé API Groq (gratuite) : https://console.groq.com/keys
- (Optionnel) Clé API Gemini pour le fallback Vision : https://aistudio.google.com/app/apikey

## Démarrage rapide

```bash
cp .env.example .env
# → Renseigner GROQ_API_KEY (obligatoire)
# → Renseigner GEMINI_API_KEY (optionnel, fallback uniquement)

docker-compose up --build

curl http://localhost:8000/health        # → {"status":"ok"}
```

## Migrations

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
```

## Pipeline OCR (S2)

```
POST /upload
  └─> Sauvegarde MinIO (pending)
  └─> Background task → extract_invoice()
        ├─ 1. OCR (run_ocr)
        │     ├─ PDF natif     → pdfplumber (texte sélectionnable)
        │     ├─ Image / scan  → EasyOCR (ar + fr)
        │     └─ PDF scanné    → PyMuPDF → image → EasyOCR
        ├─ 2. Normalisation texte (chiffres AR→latin, dates → ISO)
        ├─ 3. Détection langue (fr / ar / mixed)
        ├─ 4. Groq llama-3.3-70b → JSON structuré
        └─ 5. Fallback Gemini Vision si confidence OCR < 60%
  └─> Invoice + Vendor + LineItems mis à jour (validated / anomaly)
```

## Endpoints disponibles (S1 + S2)

| Méthode | Route | Description |
|---------|-------|-------------|
| GET  | /health | Health check |
| POST | /upload | Upload + pipeline OCR/extraction automatique |
| GET  | /invoices | Liste toutes les factures |
| GET  | /invoices/{id} | Détail d'une facture + URL fichier |
| POST | /process/{id} | Relance le pipeline OCR + extraction sur une facture existante |
| GET  | /dashboard | Statistiques globales |

## Structure du projet

```
invoiceagent/
├── docker-compose.yml          ← worker Celery désactivé (pas encore câblé, voir S3)
├── .env.example                ← GROQ_API_KEY (requis) + GEMINI_API_KEY (fallback)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt        ← + easyocr, pdfplumber, groq
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial_schema.py
│   └── app/
│       ├── main.py
│       ├── core/
│       │   ├── config.py       ← GROQ_API_KEY + GEMINI_API_KEY (fallback)
│       │   └── database.py
│       ├── models/models.py
│       ├── services/
│       │   ├── ocr.py          ← pdfplumber + EasyOCR + normalisation AR/FR
│       │   ├── llm_client.py   ← Client Groq centralisé
│       │   ├── extraction.py   ← OCR → Groq → fallback Gemini Vision
│       │   └── storage.py      ← MinIO upload / download / presigned URL
│       └── api/routes/
│           ├── health.py
│           ├── upload.py
│           ├── invoices.py
│           ├── process.py      ← NOUVEAU : POST /process/{id}
│           └── dashboard.py
```

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| API FastAPI | http://localhost:8000 | — |
| API Docs | http://localhost:8000/docs | — |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin123 |
| PostgreSQL | localhost:5432 | invoiceagent / invoiceagent_pass |
| Redis | localhost:6379 | — |

## Notes

- Le worker Celery est commenté dans `docker-compose.yml` : aucune tâche n'est encore définie
  (`app/worker.py` n'existe pas). Le traitement OCR/extraction tourne via `BackgroundTasks` FastAPI.
  Il sera réactivé en S3 avec l'orchestration LangGraph.
- EasyOCR télécharge ses modèles (ar + fr) au premier lancement — le premier `docker-compose up`
  sera donc plus lent que les suivants.
