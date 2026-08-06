# Platform & Deployment Documentation

Production deployment, monitoring, and platform-specific guides.

## Deployment

### Production Deployment
- **Production Readiness** — Pre-flight checklist ([operations/production-readiness.md](../operations/production-readiness.md))
- **Deployment Guide** — Step-by-step deployment ([deployment/DEPLOYMENT_GUIDE.md](../deployment/DEPLOYMENT_GUIDE.md))
- **Rollback Procedure** — Emergency rollback

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
- **MenuBar Guide** — MenuBar app overview ([archive/menubar/MENUBAR_GUIDE.md](../archive/menubar/MENUBAR_GUIDE.md))

### Mobile (React Native)
- **Mobile Quick Start** — Getting started ([archive/mobile/MOBILE_QUICK_START.md](../archive/mobile/MOBILE_QUICK_START.md))
- **React Native Architecture** — Architecture overview ([archive/mobile/REACT_NATIVE_ARCHITECTURE.md](../archive/mobile/REACT_NATIVE_ARCHITECTURE.md))

### Database
- **Database Migration Guide** — Alembic migrations ([archive/legacy/DATABASE_MIGRATION_GUIDE.md](../archive/legacy/DATABASE_MIGRATION_GUIDE.md))

## Specialized Setup

### Audio/Video
- **FFMPEG Setup** — FFMPEG configuration ([archive/legacy/FFMPEG_SETUP.md](../archive/legacy/FFMPEG_SETUP.md))

### Authentication
- **NextAuth Production Setup** — NextAuth configuration ([archive/oauth/nextauth_production_setup.md](../archive/oauth/nextauth_production_setup.md))

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
| Desktop (MenuBar) | ✅ Full Support | [MenuBar Guide](../archive/menubar/MENUBAR_GUIDE.md) |
| Mobile (iOS/Android) | ✅ Full Support | [Mobile Quick Start](../archive/mobile/MOBILE_QUICK_START.md) |
| Personal Edition | ✅ Full Support | [Personal Edition](../operations/personal-edition.md) |

## See Also

- **Development Guide** — Local development ([development/setup.md](../development/setup.md))
- **API Documentation** — API endpoints ([api/OVERVIEW.md](../api/OVERVIEW.md))
- **Integration Guide** — Third-party integrations ([integrations/OVERVIEW.md](../integrations/OVERVIEW.md))

---

*Last Updated: August 2026*
