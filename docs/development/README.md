# Development Documentation

Development setup, coding standards, and contribution guidelines.

## 📚 Quick Navigation

### Getting Started
- **[Development Setup](DEVELOPMENT_SETUP.md)** - Local development environment
- **[METHODOLOGY](../development/METHODOLOGY.md)** - Development methodology (in lowercase folder)

### Code Quality
- **[API Development](API_DEVELOPMENT.md)** - API development standards
- **[Code Quality](../development/code-quality.md)** - Testing and style guidelines

### Integration Development
- **[Contributing Integrations](CONTRIBUTING_INTEGRATIONS.md)** - Integration contribution guide

### Episodic Memory
- **[Episodic Memory Implementation](EPISODIC_MEMORY_IMPLEMENTATION.md)** - Memory system implementation
- **[Episodic Memory Quick Start](EPISODIC_MEMORY_QUICK_START.md)** - Quick start guide

## 🛠️ Development Setup

```bash
# Clone repository
git clone https://github.com/rush86999/atom.git
cd atom

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd frontend-nextjs
npm install

# Start development servers
# Backend: cd backend && python -m uvicorn main:app --reload
# Frontend: cd frontend-nextjs && npm run dev
```

## 📝 Coding Standards

- **Python**: PEP 8 compliant, type hints required
- **TypeScript**: ESLint + Prettier configured
- **Testing**: pytest for backend, Jest for frontend
- **Documentation**: Update docs with code changes

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend-nextjs
npm test

# E2E tests
pytest backend/tests/e2e_ui/ -v
```

## 📖 Related Documentation

- **[Development (lowercase)](../development/README.md)** - Additional development docs
- **[API Documentation](../API/README.md)** - API reference
- **[Testing](../testing/README.md)** - Testing guides

> **Note**: This folder contains uppercase development documentation. Additional development docs are in the `development/` (lowercase) folder.

---

*Last Updated: April 12, 2026*
