# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


version = __import__('flask_spec').__version__


def read(fname):
    with open(fname) as fp:
        content = fp.read()
    return content


setup(
    name='Flask-Spec',
    long_description=read('README.rst'),
    long_description_content_type="text/markdown",
    version=version,
    description=(
        'A lightweight wrapper around apispec for extracting OpenApi specs'
        ' from flask project.'
    ),
    author='Angelchev Artem',
    author_email='artangelchev@gmail.com',
    url='https://github.com/ArtemAngelchev/flask-spec',
    keywords=[
        'swagger', 'apispec', 'openapi', 'documentation', 'docs', 'api', 'rest',
    ],
    install_requires=[
        'Flask>=0.10',
        'marshmallow>=2.0.0',
        'apispec>=0.17.0',
        'markdown2>=2.0.0',
    ],
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
    ],
)
