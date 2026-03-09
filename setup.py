from setuptools import setup, find_packages

setup(
    name="graphns",
    version="2.0.0",
    description="Graph-based namespaces with OCaml-style module semantics for Python",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    author="",
    python_requires=">=3.10",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
    extras_require={
        "dev": ["pytest"],
    },
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
