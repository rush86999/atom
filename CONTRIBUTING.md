# Contributing to Atom

Thank you for your interest in contributing to Atom, the AI-powered business automation platform!

## Getting Started

### Development Setup

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for complete development setup instructions, including:
- Security requirements
- Testing procedures
- Deployment guidelines
- Background task queue setup

### Quick Start

```bash
# Clone the repository
git clone https://github.com/rush8699/atom.git
cd atom

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start development server
python -m uvicorn main:app --reload --port 8000
```

## Contribution Guidelines

### Making Changes

1. **Fork the repository** and create your feature branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following our code standards
   - Follow existing code style and patterns
   - Add tests for new functionality
   - Update documentation as needed

3. **Test thoroughly**
   ```bash
   # Run all tests
   pytest tests/ -v

   # Run specific test files
   pytest tests/test_governance_streaming.py -v
   ```

4. **Commit your changes** with clear, descriptive messages
   ```bash
   git add .
   git commit -m "feat: add description of your changes"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Standards

- **Python**: Follow PEP 8 guidelines
- **TypeScript/React**: Follow existing patterns in `frontend-nextjs/`
- **Tests**: Maintain test coverage above 80%
- **Documentation**: Update relevant docs in `docs/` directory

### Areas Where We Need Help

- **Core Features**: Agent governance, episodic memory, canvas system
- **Integrations**: New service integrations (see [backend/docs/CONTRIBUTING_INTEGRATIONS.md](backend/docs/CONTRIBUTING_INTEGRATIONS.md))
- **Testing**: Test coverage and edge cases
- **Documentation**: Guides, examples, and API documentation
- **Mobile**: React Native implementation (see [mobile/docs/REACT_NATIVE_ARCHITECTURE.md](mobile/docs/REACT_NATIVE_ARCHITECTURE.md))

## Project Structure

```
atom/
├── backend/           # Python FastAPI backend
│   ├── core/         # Core services and models
│   ├── api/          # API endpoints
│   ├── tools/        # Agent tools
│   └── tests/        # Backend tests
├── frontend-nextjs/  # Next.js frontend
├── mobile/           # React Native mobile app
├── docs/             # Documentation
└── tests/            # Integration tests
```

## Documentation

- **[docs/INDEX.md](docs/INDEX.md)** - Complete documentation index
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Development setup guide
- **[backend/docs/CONTRIBUTING_INTEGRATIONS.md](backend/docs/CONTRIBUTING_INTEGRATIONS.md)** - Integration contribution guide
- **[CLAUDE.md](CLAUDE.md)** - Project architecture and context

## Code of Conduct

### Our Pledge

We are committed to making participation in our community a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Being respectful and inclusive
- Welcoming new contributors
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment or discriminatory language
- Personal attacks or insulting comments
- Public or private harassment
- Publishing others' private information without permission
- Unprofessional conduct

## Getting Help

### Resources

- **Documentation**: [docs/INDEX.md](docs/INDEX.md)
- **Issues**: [GitHub Issues](https://github.com/rush8699/atom/issues)
- **Architecture**: See [CLAUDE.md](CLAUDE.md) for project context

### Asking Questions

1. Check existing documentation first
2. Search existing GitHub issues
3. Create a new issue with:
   - Clear description of the question
   - Relevant code snippets
   - Steps already tried

## Pull Request Process

1. **Update documentation** if you've changed functionality
2. **Add tests** for new features or bug fixes
3. **Ensure all tests pass** before submitting
4. **Update CHANGELOG.md** (if applicable)
5. **Request review** from maintainers

### PR Checklist

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Commit messages follow conventions
- [ ] PR description clearly explains changes

## License

By contributing to Atom, you agree that your contributions will be licensed under the same license as the project.

## Acknowledgments

Thank you for contributing to Atom! Every contribution helps make the platform better for everyone.
