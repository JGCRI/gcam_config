import sys
from setuptools import setup


with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="gcam_config",
    version="0.1.0",
    description="Tools for manipulating a GCAM configuration XML",
    url="https://github.com/JGCRI/gcam_config",
    author="Pralit Patel",
    author_email="pralit.patel@pnnl.gov",
    packages=["gcam_config"],
    install_requires=requirements,
    include_package_data=False
    )
