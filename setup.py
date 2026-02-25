from setuptools import setup, find_packages


setup(
    name="cockpit-agent-demo",
    version="0.1.0",
    description="Python-only demo for an intelligent cockpit agent",
    packages=find_packages(include=["services*", "libs*"]),
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.110.0",
        "requests>=2.31.0",
        "uvicorn>=0.24.0",
    ],
)
