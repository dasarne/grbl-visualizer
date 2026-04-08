"""Setup configuration for GRBL Visualizer."""

from setuptools import setup, find_packages

setup(
    name="grbl-visualizer",
    version="0.1.0",
    description="GRBL G-Code Visualizer & Analyzer for CNC Machines",
    author="dasarne",
    python_requires=">=3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "grbl-visualizer=src.main:main",
        ],
    },
    install_requires=[
        "PyQt6>=6.4.0",
        "numpy>=1.24.0",
        "matplotlib>=3.7.0",
    ],
)
