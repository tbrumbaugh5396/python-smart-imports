#!/usr/bin/env python3
"""
Setup script for Smart Import

This allows the package to be installed as:
    pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]
else:
    requirements = [
        # Smart Import has minimal dependencies - only standard library modules
    ]

setup(
    name="smart-import",
    version="1.0.0",
    author="Smart Import Team",
    author_email="",
    description="A utility for intelligent module imports in Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/smart-import",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },

    include_package_data=True,
    zip_safe=False,
    keywords="python import module utility smart dynamic",
    project_urls={
        "Bug Reports": "https://github.com/your-username/smart-import/issues",
        "Source": "https://github.com/your-username/smart-import",
        "Documentation": "https://github.com/your-username/smart-import/blob/main/README.md",
    },
)
