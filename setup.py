#!/usr/bin/env python

from setuptools import setup

setup(
    name='django-rt',
    version='0.3.1',
    description='A framework for implementing real-time APIs in Django web applications',
    author='James Hannington',
    author_email='jam.hann@gmail.com',
    url='https://github.com/jhannington/django-rt',
    license='BSD',
    zip_safe=False,

    packages=['django_rt', 'django_rt.couriers'],
    install_requires=[
        'Django>=1.7',
        'redis>=2.10',
    ],

    extras_require={
        'asyncio': [
            'aiohttp>=0.18.4',
            'asyncio-redis>=0.14.1',
        ],
        'gevent': [
            'gevent>=1.1rc1',
            'urllib3>=1.12',
        ],
    },
    scripts=['django_rt/bin/djangort-courier.py'],
    entry_points={
        'console_scripts': [
            'djangort-courier = django_rt.runcourier:main',
        ],
    },

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Server',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
