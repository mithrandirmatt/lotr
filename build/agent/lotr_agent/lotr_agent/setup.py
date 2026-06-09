from setuptools import setup, find_packages

setup(
    name="lotr_agent",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "llama-cpp-python",
        "torch",
    ],
)