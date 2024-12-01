from setuptools import setup, find_packages

setup(
    name="nytex-fireworks",
    version="0.1",
    description="NyTex Fireworks Square catalog management and image processing",
    author="Josh Goble",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "sqlalchemy>=2.0.0",
        "pydantic>=2.4.2",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        "squareup>=39.0.0.20241120",
        "beautifulsoup4>=4.12.2",
        "PyYAML>=6.0.1",
        "requests>=2.31.0",
        "Pillow>=10.0.0",
        "python-Levenshtein>=0.21.1",
        "fuzzywuzzy>=0.18.0",
        "ratelimit>=2.2.1",
        "cachetools>=4.2.4",
    ],
    python_requires=">=3.9",
) 