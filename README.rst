Django-RT
=========

:Current version: 0.3.1 pre-alpha

Django-RT is a framework for implementing real-time APIs in Django web applications. This framework follows the traditional publish/subscribe methodology, using Redis as the pub/sub provider.

Django-RT consists of two major components:

* Application API: This provides the necessary functionality to allow you to easily add a real-time API to your Django application.
* "Courier" HTTP server: A lightweight, asynchronous server designed solely to deliver real-time messages to web clients.

----

**WARNING**: Django-RT is currently in **pre-alpha**  stages of development, and is not ready for public consumption. Expect major API changes and, potentially, security risks in pre-alpha releases. Use in production at your own risk!

----

Uses
====
* Web chat
* User notifications
* Real-time charts (server monitoring, stock tickers, etc)

Features
========
* Simple to integrate with any existing Django project
* Trivial client-side JavaScript implementation with SSE (Server-Sent Events); no third-party libraries needed with modern browsers.
* Asynchronous server design to handle many long-running client connections from a single thread
* Decoupled server architecture allows for the use of blocking code (database access, cache access, etc) in callbacks, without compromising the operation of the delivery server
* Deployable on existing Heroku apps, using uWSGI

Requirements
============
* Django >= 1.7
* Python >= 3.4 (2.7+ support planned)
* A Redis server (TODO: minimum Redis version)

Deployment
==========
Courier server
---------------
There are currently 2 production servers to choose from:

* aiohttp/asyncio (recommended): Python >= 3.4
* gevent WSGI: Python >= 3.4

Protocols
---------
SSE (Server-Sent Events) is the only delivery protocol currently supported.

Limitations
===========
* Only one-way delivery is currently supported (server to client). Messages originating from the client should use a conventional AJAX request. This should be sufficient for the majority of applications.
* Real-time functionality can only be added to Django Class-Based Views (CBVs). Older function-style views are not supported.

How it works
============
TODO
