# Atom Platform - Production Deployment Guide

This guide covers deploying the Atom platform to production using Docker Compose.

## Prerequisites

- Docker 24+ and Docker Compose V2
- A server with 4GB+ RAM
- Domain name with SSL certificate (recommended)

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone git@github.com:rush86999/atom.git
   cd atom
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and fill in required values:
   # - POSTGRES_PASSWORD (use a strong password)
   # - JWT_SECRET_KEY (openssl rand -hex 32)
   # - BYOK_ENCRYPTION_KEY (openssl rand -hex 32)
   # - AI provider keys (at least one)
   ```

3. **Start the stack**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

4. **Run database migrations**:
   ```bash
   docker compose exec atom-backend alembic upgrade head
   ```

5. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8001/docs

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | ✅ | Database password |
| `JWT_SECRET_KEY` | ✅ | Authentication token signing |
| `BYOK_ENCRYPTION_KEY` | ✅ | AI key encryption |
| `OPENAI_API_KEY` | One AI key | OpenAI API access |
| `ANTHROPIC_API_KEY` | One AI key | Anthropic Claude access |
| `TAVILY_API_KEY` | Optional | Web search capability |

## Health Checks

- Backend: `curl http://localhost:8001/health`
- Frontend: `curl http://localhost:3000`

## Scaling

For high availability, consider:
- Using an external managed PostgreSQL (RDS, Cloud SQL)
- Deploying multiple backend replicas behind a load balancer
- Using Redis for session and cache (already in docker-compose.production.yml)

## Monitoring

The `deployment/docker-compose.production.yml` includes Prometheus and Grafana for observability. Access Grafana at http://localhost:3001 (default password: admin).
