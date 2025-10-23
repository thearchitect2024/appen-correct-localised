#!/usr/bin/env python3
"""
Setup script for AppenCorrect package.
"""

from setuptools import setup, find_packages
import os

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

# Filter out development dependencies
install_requires = [req for req in requirements if not req.startswith("pytest") and not req.startswith("pre-commit")]

setup(
    name="appencorrect",
    version="2.0.0",
    author="Appen Automation Solutions Team",
    author_email="rraught@appen.com",
    description="Advanced AI-Powered Text Correction & Comment Quality Assessment",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Appen/AppenCorrect",
    project_urls={
        "Bug Tracker": "https://github.com/Appen/AppenCorrect/issues",
        "Documentation": "https://github.com/Appen/AppenCorrect#readme",
        "Source Code": "https://github.com/Appen/AppenCorrect",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Text Processing :: Linguistic",
        "Topic :: Software Development :: Quality Assurance",
        "License :: Other/Proprietary License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=install_requires,
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-flask>=1.3.0",
            "pytest-cov>=4.1.0",
            "pre-commit>=3.6.0",
        ],
        "lingua": [
            "lingua-language-detector>=2.0.2",
        ],
        "production": [
            "gunicorn>=21.2.0",
            "waitress>=3.0.0",
        ],
    },
    include_package_data=True,
    package_data={
        "appencorrect": ["templates/*.html"],
    },
    # entry_points={
    #     "console_scripts": [
    #         "appencorrect=appencorrect.cli:main",
    #     ],
    # },
    keywords="text correction grammar spelling ai nlp quality assessment",
    license="Proprietary",
) 