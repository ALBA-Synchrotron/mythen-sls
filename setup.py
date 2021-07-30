# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages

TESTING = any(x in sys.argv for x in ["test", "pytest"])

requirements = ["numpy"]

setup_requires = []
if TESTING:
    setup_requires += ["pytest-runner"]
test_require = ["pytest", "pytest-cov"]
extras_require = {
    "simulator": ["pyyaml", "toml", "gevent", "scipy"],
    "gui": ["pyqtgraph"],
    "lima": ["lima-toolbox"],  # one day lima may be in pypi
    "server": ["fabric"],
}
extras_require["all"] = list(set.union(*(set(i) for i in extras_require.values())))

with open("README.md") as f:
    description = f.read()


setup(
    author="Jose Tiago Macara Coutinho",
    author_email="coutinhotiago@gmail.com",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8"
    ],
    description="SLS detector (library + lima (CLI and tango-ds) + simulator + GUI)",
    long_description=description,
    long_description_content_type="text/markdown",
    entry_points={
        "console_scripts": [
            "sls-gui=sls.gui:main [gui]",
            "sls-simulator=sls.simulator:main [simulator]",
            "sls-lima=sls.lima.camera:main [lima]",
            "sls-lima-tango-server=sls.lima.tango:main [lima]"
        ],
        "Lima_camera": [
            "MythenSLS=sls.lima.camera"
        ],
        "Lima_tango_camera": [
            "MythenSLS=sls.lima.tango"
        ],
        "limatb.cli.camera": [
            'MythenSLS=sls.lima.cli:mythensls [lima]'
        ],
        "limatb.cli.camera.scan": [
            "MythenSLS=sls.lima.cli:scan [lima]"
        ],
    },
    install_requires=requirements,
    license="MIT license",
    include_package_data=True,
    keywords="mythen, sls, simulator",
    name="sls-detector",
    packages=find_packages(include=["sls"]),
    package_data={
        "sls": ["*.ui"]
    },
    setup_requires=setup_requires,
    test_suite="tests",
    tests_require=test_require,
    extras_require=extras_require,
    python_requires=">=3.5",
    url="https://github.com/alba-synchrotron/sls-detector",
    version="1.0.1",
    zip_safe=True
)
