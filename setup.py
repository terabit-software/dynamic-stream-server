try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup


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
    requires = [
        'futures',
    ]
)