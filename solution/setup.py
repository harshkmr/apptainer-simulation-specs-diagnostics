from setuptools import find_packages, setup

setup(
    name="apptainer_diag",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "apptainer-diag = apptainer_diag.cli:main",
        ],
    },
    python_requires=">=3.8",
)
