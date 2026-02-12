# Technology Stack

**Analysis Date:** 2026-02-10

## Languages

**Primary:**
- Python 3.11 - Backend API services, AI agents, data processing
- TypeScript 4.9+ - Frontend React desktop app
- JavaScript - Frontend React components, Tauri desktop app

**Secondary:**
- SQL - Database operations (PostgreSQL, SQLite)
- HTML/CSS/JS - Canvas components, web interfaces
- Bash - Scripting, deployment automation

## Runtime

**Environment:**
- Python 3.11+ (backend)
- Node.js 18+ (frontend, mobile)
- Expo SDK 50 (mobile apps)

**Package Managers:**
- pip (Python)
- npm (JavaScript/Node.js)
- yarn (some JS packages)
- uv (optional Python alternative)

**Lockfiles:**
- requirements.txt (Python)
- package.json (JavaScript/Node.js)
- yarn.lock (where applicable)

## Frameworks

**Core:**
- FastAPI 0.104+ - Main backend web framework
- React 18.2+ - Frontend UI desktop app
- React Native 0.73.6 - Mobile app framework
- Tauri 1.5.3 - Desktop app wrapper
- Expo 50.0+ - Mobile development platform

**Testing:**
- pytest 7.4+ - Python unit/integration tests
- pytest-asyncio 0.21+ - Async testing support
- hypothesis 6.92+ - Property-based testing
- jest 29.7+ - JavaScript/React testing
- @testing-library/react-native - React Native testing

**Build/Dev:**
- uvicorn - ASGI server for FastAPI
- gunicorn 21.2.0 - Production WSGI server
- playwright 1.40.0 - Browser automation
- alembic 1.12+ - Database migrations
- ESLint - Code linting
- Prettier - Code formatting

## Key Dependencies

**Critical:**
- SQLAlchemy 2.0+ - ORM and database toolkit
- Pydantic 2.0+ - Data validation and serialization
- OpenAI 1.0+ - LLM integration
- Anthropic 0.3+ - Claude LLM integration
- transformers 4.30+ - HuggingFace models
- torch 2.0+ - PyTorch ML framework
- fastembed 0.2+ - Fast local embeddings
- lancedb 0.5.3+ - Vector database (episodic memory)
- redis 4.5+ - Caching and message broker

**Infrastructure:**
- WebSocket 11+ - Real-time communication
- httpx 0.24+ - Async HTTP client
- aiohttp 3.8+ - Async HTTP server
- asyncpg - PostgreSQL async driver
- aiosqlite - SQLite async driver

**AI/ML:**
- sentence-transformers 2.2+ - Text embeddings
- instructor 1.0+ - Structured output from LLMs
- opencv-python-headless 4.8+ - Image processing
- Pillow 10.0+ - Image manipulation
- PyPDF2 3.0+ - PDF processing
- openpyxl 3.1+ - Excel file handling

**Authentication & Security:**
- python-jose[cryptography] 3.3+ - JWT handling
- passlib[bcrypt] 1.7+ - Password hashing
- bcrypt 4.0+ - Cryptographic hashing
- cryptography 41.0+ - Cryptographic primitives
- python-multipart 0.0.6+ - Form handling
- pyotp 2.6+ - Two-factor authentication

## Configuration

**Environment:**
- Environment variables for sensitive data
- Configuration classes using dataclasses
- Feature flags via environment variables
- Development/production configurations

**Build:**
- TypeScript configuration for type checking
- ESLint configuration for code quality
- Jest configuration for testing
- FastAPI middleware for CORS, rate limiting

## Platform Requirements

**Development:**
- Python 3.11+
- Node.js 18+
- PostgreSQL (optional, defaults to SQLite)
- Redis (optional, for caching)
- Playwright browsers for automation

**Production:**
- Linux servers (tested on various distributions)
- PostgreSQL recommended for scalability
- Redis for high-performance caching
- Nginx/Apache for reverse proxy
- Docker support via docker-compose

---

*Stack analysis: 2026-02-10*