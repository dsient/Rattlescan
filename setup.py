from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="Rattlescan",
    version="1.0.0",
    author="Walker Caskey",
    author_email="w.caskey7@gmail.com",
    description="Forensic metadata analysis and secure file cleaning tool for CLI environments.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dsient/rattlescan",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Topic :: Security",
        "Topic :: System :: Filesystems",
    ],
    python_requires=">=3.8",
    install_requires=[
        "python-magic>=0.4.27",
        "Pillow>=9.0.0",
        "PyPDF2>=3.0.0",
        "mutagen>=1.45.0",
        "pytermgui>=7.0.0",
    ],
    entry_points={
        "console_scripts": [
            "rattlescan=rattlescan.cli:main",
        ],
    },
)