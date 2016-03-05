import os
import sys
import signal
import argparse
import re
import stat
import logging

from django_rt import VERSION, VERSION_STATUS

DEFAULT_ADDR = '0.0.0.0'
DEFAULT_PORT = 8080

def main():
    # Parse command line
    parser = argparse.ArgumentParser(description='Run a Django-RT courier server.')
    parser.add_argument('server_type',
        choices=['asyncio', 'gevent'],
        help='server type'
    )
    parser.add_argument('addrport',
        nargs='?',
        default=str(DEFAULT_PORT),
        help='TCP port and/or address to listen on'
    )
    parser.add_argument('--unix-socket',
        metavar='FILE',
        help='listen on a Unix domain socket instead of TCP; FILE must specify a valid file path'
    )
    parser.add_argument('--django-url',
        metavar='FILE',
        help='URL to a running Django instance (overrides RT_DJANGO_URL setting); protocol may be "http" or "http+unix"'
    )
    parser.add_argument('--debug',
        action='store_const',
        const=True,
        help='log debug messages'
    )
    args = parser.parse_args()

    # Show version
    print('Django-RT version %s (%s)' % (VERSION, VERSION_STATUS))

    # Show pre-alpha warning banner
    print(
"""
********************************************************************************
*                                                                              *
* WARNING: Django-RT is currently in PRE-ALPHA stages of development, and is   *
* not ready for public consumption. Expect major API changes and, potentially, *
* security risks in pre-alpha releases. Use in production at your own risk!    *
*                                                                              *
********************************************************************************
""")

    # Enable logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Parse addrport and unix_socket args
    if args.unix_socket:
        addr = None
        port = None
        unix_socket = args.unix_socket
    else:
        unix_socket = None
        # Split addrport if possible, otherwise assume just the port has been given
        try:
            addr, port = args.addrport.split(':')
        except ValueError:
            addr = DEFAULT_ADDR
            port = args.addrport

        # Default addr if addr is empty (i.e. user gave addrport in the form ':PORT')
        if not addr:
            addr = DEFAULT_ADDR

        # Check port is an integer
        try:
            port = int(port)
        except ValueError:
            print('addrport must be in either the form "IP:PORT" or "PORT"', file=sys.stderr)
            sys.exit(1)

    if unix_socket:
        # Attempt to remove socket file if it already exists and is a socket.
        try:
            res = os.stat(unix_socket)        
            if stat.S_ISSOCK(res.st_mode):
                os.unlink(unix_socket)
        except FileNotFoundError:
            pass

    # Import appropriate server class and create instance
    if args.server_type == 'asyncio':
        from django_rt.couriers.asyncio_courier import AsyncioCourier
        server = AsyncioCourier()
    elif args.server_type == 'gevent':
        from django_rt.couriers.gevent_courier import GeventCourier
        server = GeventCourier()

    # Trap signals to shut down gracefully
    def quit_handler(signum, frame):
        signames = {
            signal.SIGTERM: 'SIGTERM',
            signal.SIGINT: 'SIGINT',
            signal.SIGQUIT: 'SIGQUIT',
        }
        signal_name = signames[signum]
        logging.info('Caught %s; shutting down...' % (signal_name,))
        server.stop()
    signal.signal(signal.SIGTERM, quit_handler)
    signal.signal(signal.SIGINT, quit_handler)
    signal.signal(signal.SIGQUIT, quit_handler)

    # Run server
    server.run(addr, port, unix_socket, args.django_url)

if __name__ == '__main__':
    main()
