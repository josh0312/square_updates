from setuptools import setup, find_packages

setup(
    name="nytex-fireworks",
    version="0.1",
    description="NyTex Fireworks Square catalog management and image processing",
    author="Josh Goble",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.4.2",
        "starlette>=0.27.0",
        "httpx>=0.25.0",
        "Pillow>=10.0.0",
        "boto3==1.34.34",
        "botocore==1.34.34",
        "urllib3>=1.25.4,<1.27",
        "beautifulsoup4==4.12.2",
        "requests==2.31.0",
        "aiohttp==3.8.1",
        "SQLAlchemy==2.0.23",
        "squareup==39.0.0.20241120",
        "python-dotenv==1.0.0",
        "PyYAML==6.0.1",
        "cachetools==4.2.4",
        "ratelimit==2.2.1",
        "fuzzywuzzy==0.18.0",
        "python-Levenshtein==0.23.0"
    ]>=0.24.0",
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