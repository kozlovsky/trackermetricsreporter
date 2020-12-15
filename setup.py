from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='trackermetricsreporter',
    author='Alexander Kozlovsky',
    description='Report anonymized metrics from IPv8 trackers',
    long_description=long_description,
    long_description_content_type='text/markdown',
    version='0.1',
    url='https://github.com/kozlovsky/trackermetricsreporter',
    packages=find_packages(),
    install_requires=[
        "hyperloglog",
        "pydantic",
        "requests",
    ],
    tests_require=[
        'pytest'
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]
)
