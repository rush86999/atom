# Platform & Deployment Documentation

Production deployment, monitoring, and platform-specific guides.

## Deployment

### Production Deployment
- **Production Readiness** — Pre-flight checklist ([operations/production-readiness.md](../operations/production-readiness.md))
- **Deployment Guide** — Step-by-step deployment ([deployment/DEPLOYMENT_GUIDE.md](../deployment/DEPLOYMENT_GUIDE.md))
- **Rollback Procedure** — Emergency rollback ([operations/rollback.md](../operations/rollback.md))

### Personal Edition
- **Personal Edition** — Local Docker setup ([operations/personal-edition.md](../operations/personal-edition.md))

### Installation
- **Installation** — Complete setup options ([getting_started/INSTALLATION.md](../getting_started/INSTALLATION.md))
- **Installation Options** — Deployment variants
- **Install Script Guide** — Automated installation

## Monitoring & Operations

### Health & Monitoring
- **Health Monitoring System** — Health check endpoints
- **Monitoring Guide** — Monitoring setup ([operations/monitoring.md](../operations/monitoring.md))
- **Performance Monitoring Setup** — Metrics and alerts
- **Performance Tuning** — Optimization strategies

### Build & CI/CD
- **Build** — Build process
- **CI/CD Pipeline** — `.github/workflows/deploy.yml`

## Platform-Specific

### Desktop (MenuBar App)
- **MenuBar Guide** — MenuBar app overview ([guides/ATOM_CLI_SKILLS_GUIDE.md](../guides/ATOM_CLI_SKILLS_GUIDE.md))

### Mobile (React Native)
- **Mobile Quick Start** — Getting started ([guides/QUICKSTART.md](../guides/QUICKSTART.md))
- **Mobile Architecture** — React Native with Expo

### Database
- **Database Migrations** — Alembic + SQLite hybrid patterns ([getting_started/INSTALLATION.md](../getting_started/INSTALLATION.md))

## Specialized Setup

### Audio/Video
- **FFMPEG Setup** — FFMPEG configuration (see [deployment/DEPLOYMENT_GUIDE.md](../deployment/DEPLOYMENT_GUIDE.md))

### Authentication
- **NextAuth Production Setup** — NextAuth configuration (see [guides/OAUTH_SETUP_CHECKLIST.md](../guides/OAUTH_SETUP_CHECKLIST.md))

## Architecture

- **Single Tenant** — Single-tenant architecture
- **Vector Embeddings** — Embedding system ([getting_started/run-with-ollama.md](../getting_started/run-with-ollama.md))

## Quick Reference

### Deployment Checklist
- [ ] Review Production Readiness
- [ ] Follow Deployment Guide
- [ ] Configure Monitoring
- [ ] Set up Health Checks
- [ ] Prepare Rollback Procedure

### Health Endpoints
```bash
curl http://localhost:8001/health/live    # Liveness
curl http://localhost:8001/health/ready   # Readiness
curl http://localhost:8001/health/metrics # Prometheus metrics
```

### Platform Support
| Platform | Status | Docs |
|----------|--------|------|
| Web | ✅ Full Support | [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md) |
| Desktop (MenuBar) | ✅ Full Support | [ATOM_CLI_SKILLS_GUIDE](../guides/ATOM_CLI_SKILLS_GUIDE.md) |
| Mobile (iOS/Android) | ✅ Full Support | [QUICKSTART](../guides/QUICKSTART.md) |
| Personal Edition | ✅ Full Support | [Personal Edition](../operations/personal-edition.md) |

## See Also

- **Development Guide** — Local development ([development/setup.md](../development/setup.md))
- **API Documentation** — API endpoints ([api/OVERVIEW.md](../api/OVERVIEW.md))
- **Integration Guide** — Third-party integrations ([integrations/OVERVIEW.md](../integrations/OVERVIEW.md))

---

*Last Updated: August 2026*