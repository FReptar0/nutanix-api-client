"""
Setup configuration for Nutanix API Client.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""

setup(
    name="nutanix-api-client",
    version="1.0.1",
    author="FReptar0",
    description="Unified system for JWT generation, XML transformation, and Nutanix API communication",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/FReptar0/nutanix-api-client",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "PyJWT>=2.8.0",
        "cryptography>=41.0.0",
        "requests>=2.31.0",
        "PyYAML>=6.0",
        "lxml>=4.9.3",
    ],
    entry_points={
        'console_scripts': [
            'nutanix-client=nutanix_client.cli:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
