import setuptools
from pathlib import Path


# Reading the long description from README.md
def read_long_description():
    try:
        return Path("README.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return "A description of RAGAnything is currently unavailable."


# Retrieving metadata from __init__.py
def retrieve_metadata():
    vars2find = ["__author__", "__version__", "__url__"]
    vars2readme = {}
    try:
        with open("./raganything/__init__.py") as f:
            for line in f.readlines():
                for v in vars2find:
                    if line.startswith(v):
                        line = (
                            line.replace(" ", "")
                            .replace('"', "")
                            .replace("'", "")
                            .strip()
                        )
                        vars2readme[v] = line.split("=")[1]
    except FileNotFoundError:
        raise FileNotFoundError("Metadata file './raganything/__init__.py' not found.")

    # Checking if all required variables are found
    missing_vars = [v for v in vars2find if v not in vars2readme]
    if missing_vars:
        raise ValueError(
            f"Missing required metadata variables in __init__.py: {missing_vars}"
        )

    return vars2readme


# Reading dependencies from requirements.txt
def read_requirements():
    deps = []
    try:
        with open("./requirements.txt") as f:
            deps = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        print(
            "Warning: 'requirements.txt' not found. No dependencies will be installed."
        )
    return deps


metadata = retrieve_metadata()
long_description = read_long_description()
requirements = read_requirements()

# Define extras_require for optional features
extras_require = {
    "image": ["Pillow>=10.0.0"],  # For image format conversion (BMP, TIFF, GIF, WebP)
    "text": ["reportlab>=4.0.0"],  # For text file to PDF conversion (TXT, MD)
    "office": [],  # Office document processing requires LibreOffice (external program)
    "markdown": [
        "markdown>=3.4.0",
        "weasyprint>=60.0",
        "pygments>=2.10.0",
    ],  # Enhanced markdown conversion
    "graphiti": [
        "graphiti-core>=0.19.0",
        "falkordb>=1.1.2,<2.0.0",
        "neo4j>=5.26.0",
        "pydantic>=2.11.5",
        "tenacity>=9.0.0",
        "diskcache>=5.6.3",
        "posthog>=3.0.0",
        "python-dotenv>=1.0.1",
    ],  # Graphiti integration with all required dependencies
    "graphiti-dev": [
        "graphiti-core>=0.19.0", 
        "falkordb>=1.1.2,<2.0.0",
        "neo4j>=5.26.0",
        "anthropic>=0.49.0",
        "groq>=0.2.0",
        "google-genai>=1.8.0",
        "voyageai>=0.2.3",
        "sentence-transformers>=3.2.1",
    ],  # Graphiti with additional model providers
    "api": [
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
        "pydantic>=2.5.0",
    ],  # FastAPI REST service
    "all": [
        "Pillow>=10.0.0", 
        "reportlab>=4.0.0",
        "markdown>=3.4.0",
        "weasyprint>=60.0",
        "pygments>=2.10.0",
        "graphiti-core>=0.19.0",
        "falkordb>=1.1.2,<2.0.0",
        "neo4j>=5.26.0",
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "python-multipart>=0.0.6",
    ],  # All optional features including Graphiti and API
}

setuptools.setup(
    name="raganything",
    url=metadata["__url__"],
    version=metadata["__version__"],
    author=metadata["__author__"],
    description="RAGAnything: All-in-One RAG System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(
        exclude=("tests*", "docs*")
    ),  # Automatically find packages
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require=extras_require,
    include_package_data=True,  # Includes non-code files from MANIFEST.in
    project_urls={  # Additional project metadata
        "Documentation": metadata.get("__url__", ""),
        "Source": metadata.get("__url__", ""),
        "Tracker": f"{metadata.get('__url__', '')}/issues"
        if metadata.get("__url__")
        else "",
    },
)
