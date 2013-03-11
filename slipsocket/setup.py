'''
Created on 11 mrt. 2013

@author: Ruud de Jong
'''

from distutils.core import setup

setup(
      name='SLIPsocket',
      version='0.1.0',
      author='Ruud de Jong',
      author_email='rhjdjong@gmail.com',
      packages=['slipsocket', 'slipsocket.test'],
      url='https://code.google.com/p/slipsocket/',
      download_url='https://code.google.com/p/slipsocket/downloads/list',
      keywords=['SLIP', 'Networking', 'Protocols', 'TCP'],
      classifiers=[
                   'Development Status :: 1 - Planning',
                   'Environment :: Other Environment',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python',
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 3',
                   'Topic :: Software Development :: Libraries :: Python Modules',
                   'Topic :: System :: Networking',
                   ],
      desciption='Python module providing the SLIP protocol over TCP sockets',
      long_description = """\
This module adds the SLIP protocol on top of the standard Python socket.
This is one way of enabling message-based communication over TCP.

This module is intended for Python developers.
It is useful in the following situations:

  * You need to implement an application that requires processes to exchange messages
    via long-standing TCP connections, and you are free to choose the method of message
    delimitation.

  * You are developing an application that must communicate with an existing
    application that uses SLIP over TCP to exchange messages."""
      )