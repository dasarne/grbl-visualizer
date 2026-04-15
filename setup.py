"""Setup configuration for GCode Lisa."""

from setuptools import setup, find_packages

setup(
    name="gcode-lisa",
    version="0.1.0",
    description="GCode Lisa - Cut with confidence. Waste less.",
    author="dasarne",
    python_requires=">=3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "gcode-lisa=src.main:main",
            "grbl-visualizer=src.main:main",
        ],
    },
    install_requires=[
        "PyQt6>=6.4.0",
        "numpy>=1.24.0",
        "matplotlib>=3.7.0",
    ],
)
