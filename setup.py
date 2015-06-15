# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup(
    name='manage.py',
    version='0.2.10',
    description='Human friendly CLI builder',
    long_description='',
    author='jean-philippe serafin',
    author_email='jps@birdback.com',
    url='https://github.com/Birdback/manage.py',
    packages=find_packages(),
    install_requires=[],
    entry_points={
        'console_scripts': [
            'manage = manager.main:main',
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
