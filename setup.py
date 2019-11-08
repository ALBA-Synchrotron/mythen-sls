# -*- coding: utf-8 -*-

"""The setup script."""

import sys
from setuptools import setup, find_packages

TESTING = any(x in sys.argv for x in ["test", "pytest"])

requirements = ['numpy']

setup_requirements = []
if TESTING:
    setup_requirements += ['pytest-runner']
test_requirements = ['pytest', 'pytest-cov']
extras_requirements = {
    'simulator': ['pyyaml', 'gevent', 'scipy'],
    'gui': ['pyqtgraph'],
    'lima': [], # one day lima may be in pypi
    'server': ['fabric']
}

setup(
    author="Jose Tiago Macara Coutinho",
    author_email='coutinhotiago@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ],
    description="Mythen SLS detector interface",
    entry_points={
        'console_scripts': [
            'sls-gui=sls.gui:main [gui]',
            'sls-simulator=sls.simulator:main [simulator]',
            'sls-lima-tango-server=sls.lima.tango:main [lima]'
        ],
        'Lima_camera': [
            'MythenSLS = sls.lima.camera'
        ],
        'Lima_tango_camera': [
            'MythenSLS = sls.lima.tango'
        ]
    },
    install_requires=requirements,
    license="MIT license",
    long_description="Myhen SLS detector library and (optional) simulator",
    include_package_data=True,
    keywords='mythen, sls, simulator',
    name='sls',
    packages=find_packages(include=['sls']),
    package_data={
        'sls': ['*.ui']
    },
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    extras_require=extras_requirements,
    python_requires='>=3.5',
    url='https://gitlab.com/tiagocoutinho/sls',
    version='0.1.0',
    zip_safe=True
)
