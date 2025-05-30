# 🔁 Automated Data Pipeline with FastAPI, PostgreSQL, MinIO & n8n

This repository provides a ready-to-run local environment for building a market intelligence and automation platform. It integrates:

- **FastAPI** (Python backend for OCR & API services)  
- **PostgreSQL** (relational data storage)  
- **MinIO** (S3-compatible object storage)  
- **n8n** (workflow engine for automation)  
- **Adminer** (lightweight database UI)  

The goal is to **automate document processing, CSV parsing, and structured data injection** into PostgreSQL, all triggered by file uploads.

---

## 🐳 Services Overview

| Service     | URL                      | Purpose                        |
|-------------|--------------------------|--------------------------------|
| FastAPI     | http://localhost:8000    | OCR & API endpoints            |
| Adminer     | http://localhost:8080    | PostgreSQL UI                  |
| MinIO UI    | http://localhost:8001    | Object-store browser           |
| MinIO API   | http://localhost:8002    | S3-compatible API              |
| n8n         | http://localhost:5678    | Automation/workflow editor     |

---

## 🛠️ Getting Started

### 1. Launch the stack

```bash
make up
```

### 2. Stop the stack

```bash
make down
```

### 3. View logs

```bash
make logs
```

---

## 🐍 Python FastAPI Application

The FastAPI backend (`python/app/main.py`) provides a comprehensive OCR and document processing API with the following features:

### Key Components

- **CORS Configuration** - Cross-origin resource sharing enabled for web clients
- **MinIO Integration** - Direct connection to object storage for file operations
- **Tesseract OCR** - Text extraction from images and PDFs
- **Multiple Upload Methods** - Support for both direct uploads and MinIO-based processing

### API Endpoints

#### OCR Processing

- **/ocr1/** - Processes files stored in MinIO, detecting file type automatically
- **/ocr2/** - Processes directly uploaded files or JSON payload with binary data


#### File Operations
- **/upload/** - Upload files directly to MinIO with automatic processing
- **/download/{filename}** - Get file metadata and binary content as a JSON list
- **/download-file/{filename}** - Stream file for direct download with proper content type

#### Database Integration

- **/api/tables** - Lists all CSV-derived tables in PostgreSQL
- **/api/table/{table_name}** - Retrieves data from a specific table
- **/generate-report-pptx/** - Creates a PowerPoint presentation based on table data

### Processing Features

- **Automatic file type detection** - Uses both file extensions and binary signatures
- **OCR for multiple formats** - Images (PNG, JPG, GIF) and multi-page PDFs
- **CSV parsing and database integration** - Converts uploaded CSV files to database tables
- **Comprehensive error handling** - Detailed error messages for troubleshooting

### Implementation Details

- Uses **pytesseract** for OCR text extraction
- Uses **pdf2image** for PDF to image conversion
- Implements temporary file handling for secure processing
- Provides both synchronous and asynchronous endpoints
- Includes content type detection for proper file handling

## 🧬 Workflow Summary

**n8n Workflow ID:** 3wKEH6VC90v3we9k

**Purpose:** Automatically ingest files from MinIO and store structured data.

1. **Webhook** — triggered on new file upload.
2. **S3** — list files in uploads/ bucket.
3. **Split Out** — iterate each file.
4. **If** — check file extension:

   **CSV branch:**
   - Download via S3 node.
   - Extract from File — parse CSV rows.
   - Code2 — generate CREATE TABLE + INSERT SQL.
   - Postgres3 — execute queries.

   **OCR branch (PDF/images):**
   - HTTP Request to FastAPI /ocr1.
   - Convert to File — wrap text.
   - Code3 — create OCR table if needed.
   - Postgres4 — execute creation.
   - Code1 — split text into rows/columns.
   - Code4 — optional enrichment.

**Key features:**
- Dynamic table names from filenames
- SQL-safe column names based on headers
- Supports any CSV structure
- Easily extendable for notifications or other outputs

---

## 🧾 Makefile Shortcuts

| Command | Description |
|---------|-------------|
| `make up` | Build & start all services (detached) |
| `make down` | Stop & remove all containers |
| `make restart` | Recreate everything |
| `make logs` | Tail all service logs |
| `make webshell` | Bash into FastAPI container |
| `make dbshell` | Bash into PostgreSQL container |
| `make n8nshell` | Bash into n8n container |
| `make build` | Rebuild Docker images |
| `make prune` | Prune unused Docker resources |

---
