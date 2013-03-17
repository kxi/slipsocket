'''
Created on 11 mrt. 2013

@author: Ruud de Jong
'''

import socket as s

_END = b'\xc0'                # SLIP <END> symbol
_ESC = b'\xdb'                # SLIP <ESC> symbol
_ESC_END = b'\xdb\xdc'        # SLIP <ESC_END> symbol
_ESC_ESC = b'\xdb\xdd'        # SLIP <ESC_ESC> symbol
_BUF_SIZE = 4096

 
def encode(data):
    '''encode(data) -> bytes object with SLIP encoded data
    
    <END> bytes are replaced with <ESC_END>,
    <ESC> bytes are replaced with <ESC_ESC>,
    the resulting bytes are delimited with <END> bytes.'''
    return _END + data.replace(_ESC, _ESC_ESC).replace(_END, _ESC_END) + _END
    
def decode(packet):
    '''decode(packet) -> bytes object without SLIP delimiters and special slip escape sequences
    
    Packet must be in format <END> <escaped-data> <END>
    Missing leading or trailing <END> symbols are allowed,
    as are multiple occurances of the <END> symbol.'''
    return packet.strip(_END).replace(_ESC_END, _END).replace(_ESC_ESC, _ESC)

    
class socket(s.socket):
    def __init__(self, family=s.AF_INET, type=s.SOCK_STREAM, proto=0, fileno=None):
        if type != s.SOCK_STREAM:
            raise ValueError('slipsocket.socket requires type=SOCK_STREAM')
        super().__init__(family, type, proto, fileno)
        self._buffer = bytearray()
        self._source = None
    
    def _refresh(self, flags):
        new_data, addr = super().recvfrom(_BUF_SIZE, flags)
        if len(new_data) == 0:
            raise RuntimeError('Socket connection closed')
        self._buffer.extend(new_data)
        self._source = addr

    def accept(self):
        conn, addr = super().accept()
        return self.__class__(conn.family, conn.type, conn.proto, conn.detach()), addr

    def sendall(self, data):
        super().sendall(encode(data))
    
    send = sendall
    
    def _recv(self, flags=0):
        # Wait until the buffer contains something different than <END> symbols
        while set(self._buffer) <= set(_END):
            self._refresh(flags)
        
        # Buffer contains at least one none <END> symbol
        # Remove all leading <END> symbols
        self._buffer = self._buffer.lstrip(_END)
        
        # Wait until the buffer contains the trailing <END> symbol
        while _END not in self._buffer:
            self._refresh(flags)
        
        # Locate the (first) trailing <END> symbol and extract the packet
        end_index = self._buffer.find(_END)
        packet = self._buffer[:end_index]
        
        # Remove the packet from the buffer, including the trailing <END> symbol
        del self._buffer[:end_index+1]
        
        # Return the decoded data and source
        return decode(packet)

    def recv(self, flags=0):
        return self._recv(flags=flags)
    
    def recvfrom(self, flags=0):
        return self._recv(flags=flags), self._source

    def recvfrom_into(self, *args, **kwargs):
        raise AttributeError('slipsocket.socket does not support recvfrom_into')
    
    def recv_into(self, *args, **kwargs):
        raise AttributeError('slipsocket.socket does not support recv_into')
    
    def recvmsg(self, *args, **kwargs):
        raise AttributeError('slipsocket.socket does not support recvmsg')
    
    def sendmsg(self, *args, **kwargs):
        raise AttributeError('slipsocket.socket does not support sendmsg')
    
    def sendto(self, *args, **kwargs):
        raise AttributeError('slipsocket.socket does not support sendto')
    

        
if hasattr(s, 'socketpair'):
    def socketpair(family=None, type=s.SOCK_STREAM, proto=s.IPPROTO_IP):
        a, b = s.socketpair(family, type, proto)
        a = socket(family, type, proto, a.detach())
        b = socket(family, type, proto, b.detach())
        return a, b


def fromfd(fd, family, type, proto=0):
    nfd = s.dup(fd)
    return socket(family, type, proto, nfd)

def create_connection(address, timeout=s._GLOBAL_DEFAULT_TIMEOUT,
                      source_address=None):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used.  If *source_address* is set it must be a tuple of (host, port)
    for the socket to bind as a source address before making the connection.
    An host of '' or port 0 tells the OS to use the default.
    """
    sock = s.create_connection(address, timeout, source_address)
    return socket(sock.family, sock.type, sock.proto, sock.detach())


