"""
Setup configuration for pip installable Atom OS package.

Personal Edition: pip install atom-os
Enterprise Edition: pip install atom-os[enterprise]

Feature flags controlled by PackageFeatureService.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text()

# Core dependencies (Personal Edition)
install_requires = [
    # Core framework
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.20.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.5",

    # Database (SQLite for Personal)
    "sqlalchemy>=2.0.0",
    "alembic>=1.8.0",

    # Authentication
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",

    # Configuration
    "python-dotenv>=1.0.0",

    # LLM providers
    "openai>=1.0.0",
    "anthropic>=0.18.0",

    # Websockets
    "websockets>=11.0",

    # HTTP client
    "httpx>=0.24.0",

    # CLI
    "click>=8.0.0",

    # Vector embeddings (local)
    "fastembed>=0.2.0",

    # Logging
    "structlog>=23.1.0",
]

# Optional dependencies for Enterprise Edition
extras_require = {
    "enterprise": [
        # PostgreSQL driver
        "psycopg2-binary>=2.9.0",

        # Redis for pub/sub (multi-user)
        "redis>=4.5.0",

        # Monitoring
        "prometheus-client>=0.17.0",

        # SSO providers
        "authlib>=1.2.0",
        "pyokta>=1.0.0",

        # Advanced analytics
        "pandas>=2.0.0",
        "numpy>=1.24.0",

        # Rate limiting
        "slowapi>=0.1.9",

        # Additional integrations
        "boto3>=1.28.0",  # AWS
        "google-cloud-storage>=2.5.0",
    ],
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "mypy>=1.0.0",
        "black>=23.0.0",
        "ruff>=0.0.280",
    ],
    "test": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "httpx>=0.24.0",
        "faker>=19.0.0",
    ],
    "all": [
        "atom-os[enterprise,dev,test]",
    ],
}

setup(
    name="atom-os",
    version="0.1.0",
    description="AI-powered business automation platform with multi-agent governance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Atom Platform",
    author_email="contact@atom-platform.dev",
    url="https://github.com/rush86999/atom",
    project_urls={
        "Bug Tracker": "https://github.com/rush86999/atom/issues",
        "Documentation": "https://github.com/rush86999/atom/tree/main/docs",
        "Source Code": "https://github.com/rush86999/atom",
    },

    packages=find_packages(exclude=["tests.*", "tests", "*.tests", "*.tests.*"]),
    include_package_data=True,

    # Python version requirement
    python_requires=">=3.11",

    # Dependencies
    install_requires=install_requires,
    extras_require=extras_require,

    # Console script entry points
    entry_points={
        "console_scripts": [
            "atom-os=cli.main:main_cli",
        ],
    },

    # Package metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],

    # Keywords for PyPI
    keywords="automation ai agents governance multi-agent llm business workflow",

    # Zip safe
    zip_safe=False,

    # Include data files
    package_data={
        "atom_os": ["templates/*", "static/*"],
    },
)
