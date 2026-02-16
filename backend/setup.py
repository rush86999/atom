"""
Setup configuration for pip installable Atom OS package.

OpenClaw Integration: Single-command installer ("pip install atom-os").
Full-featured Atom with governance-first architecture.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text()

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, "r") as f:
        requirements = [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

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
    install_requires=requirements,

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
