# Platform & Deployment Documentation

Production deployment, monitoring, and platform-specific guides.

## Deployment

### Production Deployment
- **Production Readiness** - Deployment checklist
- **[Production Readiness Report](../archive/legacy/PRODUCTION_READINESS_REPORT.md)** - Readiness assessment
- **Deployment** - Deployment overview
- **Deployment Guide** - Step-by-step deployment
- **Rollback Procedure** - Emergency rollback

### Personal Edition
- **Personal Edition** - Local Docker setup
- **[Personal Edition Guide](../archive/legacy/PERSONAL_EDITION_GUIDE.md)** - Complete guide

### Installation
- **Installation** - Installation overview
- **Installation Options** - Deployment options
- **Install Script Guide** - Automated installation
- **Mac Mini Install** - Mac-specific setup
- **[Native Setup](../archive/legacy/NATIVE_SETUP.md)** - Native builds

## Monitoring & Operations

### Health & Monitoring
- **Health Monitoring System** - Health check endpoints
- **Monitoring Guide** - Monitoring setup
- **Performance Monitoring Setup** - Metrics and alerts
- **Performance Tuning** - Optimization strategies

### Build & CI/CD
- **Build** - Build process
- **[CI Fixes](../archive/legacy/CI_FIXES.md)** - CI/CD troubleshooting

## Platform-Specific

### Desktop (MenuBar App)
- **[MenuBar Guide](../archive/menubar/MENUBAR_GUIDE.md)** - MenuBar app overview
- **[MenuBar Complete Final](../archive/menubar/MENUBAR_COMPLETE_FINAL.md)** - Completion status
- **[MenuBar Deployment](../archive/menubar/MENUBAR_DEPLOYMENT.md)** - Deployment guide
- **[MenuBar Test Status](../archive/menubar/MENUBAR_TEST_STATUS_FEB_5.md)** - Test results
- **Desktop Coverage** - Feature coverage
- **[Desktop and Browser Feature Proposal](../archive/legacy/DESKTOP_AND_BROWSER_FEATURE_PROPOSAL.md)** - Feature planning
- **Desktop Testing Guide** - Testing documentation

### Mobile (React Native)
- **[Mobile Deployment](../archive/mobile/MOBILE_DEPLOYMENT.md)** - Mobile deployment
- **[Mobile Quick Start](../archive/mobile/MOBILE_QUICK_START.md)** - Getting started
- **Mobile Testing Guide** - Mobile testing
- **[Mobile User Guide](../archive/mobile/MOBILE_USER_GUIDE.md)** - End-user guide
- **[React Native Architecture](../archive/mobile/REACT_NATIVE_ARCHITECTURE.md)** - Architecture overview

### Database
- **[Database Migration Guide](../archive/legacy/DATABASE_MIGRATION_GUIDE.md)** - Alembic migrations
- **PostgreSQL Production Guide** - Production setup
- **[PostgreSQL Verification Report](../archive/legacy/POSTGRESQL_VERIFICATION_REPORT.md)** - Verification results

## Specialized Setup

### Audio/Video
- **[FFMPEG Setup](../archive/legacy/FFMPEG_SETUP.md)** - FFMPEG configuration
- **[LLMA CPP Setup Guide](../archive/legacy/LLMA_CPP_SETUP_GUIDE.md)** - LLM.cpp setup

### Authentication
- **[NextAuth Production Setup](../archive/oauth/nextauth_production_setup.md)** - NextAuth configuration

## Architecture

- **Single Tenant** - Single-tenant architecture
- **Vector Embeddings** - Embedding system

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
| Web | ✅ Full Support | Deployment Guide |
| Desktop (MenuBar) | ✅ Full Support | [MenuBar Guide](../archive/menubar/MENUBAR_GUIDE.md) |
| Mobile (iOS/Android) | ✅ Full Support | [Mobile Quick Start](../archive/mobile/MOBILE_QUICK_START.md) |
| Personal Edition | ✅ Full Support | Personal Edition |

## See Also

- **Development Guide** - Local development
- **API Documentation** - API endpoints
- **Integration Guide** - Third-party integrations

---

*Last Updated: April 5, 2026*
