#! coding: utf-8
import sys
try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

py_version = sys.version_info[:2]

# All versions
install_requires = [
    'tornado',
    'setuptools',
    'makeobj',
    'pymongo',
]

if py_version < (3, 0):
    install_requires += [
        'python-daemon'
    ]
else:
    install_requires += [
        'python-daemon-3K'
    ]


if py_version < (3, 2):
    install_requires += [
        'futures',
        'configparser',
    ]

if py_version in [(2, 6), (3, 0)]:
    install_requires += [
        'importlib',
        'ordereddict',
    ]


setup(
    name='Dynamic Stream Server',
    version = '0.7',
    description = 'Dynamic video streaming system',
    author = [
        'João Bernardo Oliveira',
        'Nelson Perez',
    ],
    author_email = 'jbvsmo@gmail.com',
    url = 'https://github.com/terabit-software/dynamic-stream-server',
    packages = [],
    install_requires = install_requires,
)
