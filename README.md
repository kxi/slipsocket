# slipsocket
Automatically exported from code.google.com/p/slipsocket

## Original readme
This module adds the SLIP protocol on top of the standard Python socket. This is one way of enabling message-based communication over TCP.

This module is intended for Python developers. It is useful in the following situations:

You need to implement an application that requires processes to exchange messages via long-standing TCP connections, and you are free to choose the method of message delimitation.
You are developing an application that must communicate with an existing application that uses SLIP over TCP to exchange messages.
