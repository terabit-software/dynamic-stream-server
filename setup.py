try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

import sys
install_requires = []
if sys.version_info < (3, 2):
    install_requires = [
        'futures',
        'configparser',
    ]


setup(
    name='Dynamic Stream Server',
    version = '0.1',
    description = 'Dynamic video streaming system',
    author = [
        'Joao Bernardo Oliveira',
        'Nelson Perez',
    ],
    author_email = 'jbvsmo@gmail.com',
    url = 'https://bitbucket.org/jbvsmo/dynamic-stream-server',
    packages = ['cetrio'],
    install_requires = install_requires,
)