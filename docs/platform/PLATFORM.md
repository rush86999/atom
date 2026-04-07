# Platform & Deployment Documentation

Production deployment, monitoring, and platform-specific guides.

## Deployment

### Production Deployment
- **[Production Readiness](PRODUCTION_READINESS.md)** - Deployment checklist
- **[Production Readiness Report](PRODUCTION_READINESS_REPORT.md)** - Readiness assessment
- **[Deployment](DEPLOYMENT.md)** - Deployment overview
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Step-by-step deployment
- **[Rollback Procedure](ROLLBACK_PROCEDURE.md)** - Emergency rollback

### Personal Edition
- **[Personal Edition](PERSONAL_EDITION.md)** - Local Docker setup
- **[Personal Edition Guide](PERSONAL_EDITION_GUIDE.md)** - Complete guide

### Installation
- **[Installation](INSTALLATION.md)** - Installation overview
- **[Installation Options](INSTALLATION_OPTIONS.md)** - Deployment options
- **[Install Script Guide](INSTALL_SCRIPT_GUIDE.md)** - Automated installation
- **[Mac Mini Install](MAC_MINI_INSTALL.md)** - Mac-specific setup
- **[Native Setup](NATIVE_SETUP.md)** - Native builds

## Monitoring & Operations

### Health & Monitoring
- **[Health Monitoring System](HEALTH_MONITORING_SYSTEM.md)** - Health check endpoints
- **[Monitoring Guide](MONITORING_GUIDE.md)** - Monitoring setup
- **[Performance Monitoring Setup](PERFORMANCE_MONITORING_SETUP.md)** - Metrics and alerts
- **[Performance Tuning](PERFORMANCE_TUNING.md)** - Optimization strategies

### Build & CI/CD
- **[Build](BUILD.md)** - Build process
- **[CI Fixes](CI_FIXES.md)** - CI/CD troubleshooting

## Platform-Specific

### Desktop (MenuBar App)
- **[MenuBar Guide](MENUBAR_GUIDE.md)** - MenuBar app overview
- **[MenuBar Complete Final](MENUBAR_COMPLETE_FINAL.md)** - Completion status
- **[MenuBar Deployment](MENUBAR_DEPLOYMENT.md)** - Deployment guide
- **[MenuBar Test Status](MENUBAR_TEST_STATUS_FEB_5.md)** - Test results
- **[Desktop Coverage](DESKTOP_COVERAGE.md)** - Feature coverage
- **[Desktop and Browser Feature Proposal](DESKTOP_AND_BROWSER_FEATURE_PROPOSAL.md)** - Feature planning
- **[Desktop Testing Guide](DESKTOP_TESTING_GUIDE.md)** - Testing documentation

### Mobile (React Native)
- **[Mobile Deployment](MOBILE_DEPLOYMENT.md)** - Mobile deployment
- **[Mobile Quick Start](MOBILE_QUICK_START.md)** - Getting started
- **[Mobile Testing Guide](MOBILE_TESTING_GUIDE.md)** - Mobile testing
- **[Mobile User Guide](MOBILE_USER_GUIDE.md)** - End-user guide
- **[React Native Architecture](REACT_NATIVE_ARCHITECTURE.md)** - Architecture overview

### Database
- **[Database Migration Guide](DATABASE_MIGRATION_GUIDE.md)** - Alembic migrations
- **[PostgreSQL Production Guide](POSTGRESQL_PRODUCTION_GUIDE.md)** - Production setup
- **[PostgreSQL Verification Report](POSTGRESQL_VERIFICATION_REPORT.md)** - Verification results

## Specialized Setup

### Audio/Video
- **[FFMPEG Setup](FFMPEG_SETUP.md)** - FFMPEG configuration
- **[LLMA CPP Setup Guide](LLMA_CPP_SETUP_GUIDE.md)** - LLM.cpp setup

### Authentication
- **[NextAuth Production Setup](nextauth_production_setup.md)** - NextAuth configuration

## Architecture

- **[Single Tenant](SINGLE_TENANT.md)** - Single-tenant architecture
- **[Vector Embeddings](VECTOR_EMBEDDINGS.md)** - Embedding system

## Quick Reference

### Deployment Checklist
- [ ] Review [Production Readiness](PRODUCTION_READINESS.md)
- [ ] Follow [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [ ] Configure [Monitoring](MONITORING_GUIDE.md)
- [ ] Set up [Health Checks](HEALTH_MONITORING_SYSTEM.md)
- [ ] Prepare [Rollback Procedure](ROLLBACK_PROCEDURE.md)

### Health Endpoints
```bash
curl http://localhost:8000/health/live    # Liveness
curl http://localhost:8000/health/ready   # Readiness
curl http://localhost:8000/health/metrics # Prometheus metrics
```

### Platform Support
| Platform | Status | Docs |
|----------|--------|------|
| Web | ✅ Full Support | [Deployment Guide](DEPLOYMENT_GUIDE.md) |
| Desktop (MenuBar) | ✅ Full Support | [MenuBar Guide](MENUBAR_GUIDE.md) |
| Mobile (iOS/Android) | ✅ Full Support | [Mobile Quick Start](MOBILE_QUICK_START.md) |
| Personal Edition | ✅ Full Support | [Personal Edition](PERSONAL_EDITION.md) |

## See Also

- **[Development Guide](DEVELOPMENT.md)** - Local development
- **[API Documentation](API.md)** - API endpoints
- **[Integration Guide](INTEGRATION.md)** - Third-party integrations

---

*Last Updated: April 5, 2026*
