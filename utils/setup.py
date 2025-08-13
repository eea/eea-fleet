#!/usr/bin/env python3
"""
Setup script for EEA Fleet Configuration Generator
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="eea-fleet-generator",
    version="1.0.0",
    author="EEA Fleet Team",
    description="Modern terminal interface for generating Rancher Fleet configurations for EEA Helm charts",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eea/helm-charts",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "eea-fleet-tui=src.main:main",
        ],
    },
)