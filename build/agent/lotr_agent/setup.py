from setuptools import setup, find_packages

setup(
    name="lotr_agent",
    version="0.1.0",
    packages=find_packages(where=".", include="lotr_agent*"),
    install_requires=[
        "llama-cpp-python>=0.2.7",
        "torch>=2.0",
        "transformers>=4.35",
        "einops>=0.6"
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    author="Your Name",
    author_email="your.email@example.com",
    description="A MoE model for coding tasks with 4-bit quantization",
    long_description="""
A specialized model for coding tasks using LLaMA 3 8B with 4-bit quantization optimization for AMD GPUs.
""",
    url="https://github.com/yourusername/lotr",
    license="MIT",
    include_package_data=True,
    zip_safe=False
)
