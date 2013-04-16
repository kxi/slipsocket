'''
Created on 11 mrt. 2013

@author: Ruud de Jong

This module provides an implementation of the SLIP protocol (RFC 1055) that can be used
to frame messages over a continuous byte stream.

The primary purpose of this module is NOT to provide IP message framing (although it
does not exclude it). The major use-cases are:

 * Communicating with a (third-party) application that uses SLIP-encoding to frame
   messages over a (persistent) TCP connection.
 * A greenfield situation where a reliable message exchange is required, but where use of
   a protocol like SCTP would be overkill.

Background:
UDP is a natural protocol for message passing, but it is not reliable. TCP is reliable,
but does not by itself provide message boundaries. Where a reliable message passing
mechanism is required, TCP or UDP by themselves are not sufficient.

As explained in the excellent Python Socket Programming HOWTO by Gordon McMillan,
when you want to use TCP to send individual messages, there are actually a number of
choices:

 - Fix length messages
 - Delimited messages
 - A length indicator in or with the message
 - Using the TCP connection for a single message only
 
 The slipsocket module provides a method to delimit messages by using the SLIP protocol
 on top of TCP. This differs from the classical use of SLIP as a layer-2 protocol for
 the transport of IP messages over e.g. serial connections. Because this module provides
 the SLIP protocol on top of TCP, none of the restrictions and considerations regarding
 bandwidth and error detection that are mentioned in RFC 1055 apply. In particular, there is
 no need to limit the size of SLIP packets to 1006.
 
 This module offers:
 
 - Basic SLIP encode and decode functions.
 - SlipReader, SlipWriter, SlipRandom, and SlipRWPair classes that wrap the corresponding 
   classesBufferedReader, BufferedWriter, BufferedRandom, and BufferedRWPair from the 
   io module with the SLIP protocol. Reads from these classes deliver decoded SLIP packets, 
   writes will push encoded SLIP packets to the underlying stream.
 - SlipSocket, slipSocketPair, slipFromFd, and createSlipConnection that provide the SLIP
   protocol over TCP connections.
'''

import socket
import io

# SLIP (RFC 1055) defines the message delimiter symbol <END> and the escape symbol <ESC>.
# Any <END> or <ESC> symbol in the message itself must be escaped, these are replaced
# with <ESC_END> and <ESC_ESC> respectively.

_END = b'\xc0'                # SLIP <END> symbol
_ESC = b'\xdb'                # SLIP <ESC> symbol
_ESC_END = b'\xdb\xdc'        # SLIP <ESC_END> symbol
_ESC_ESC = b'\xdb\xdd'        # SLIP <ESC_ESC> symbol

 
def encode(data):
    '''encode(data) -> bytes object with SLIP encoded data
    
    <END> bytes are replaced with <ESC_END>,
    <ESC> bytes are replaced with <ESC_ESC>,
    the resulting bytes are delimited with <END> bytes.
    
    >>> encode(b'hello')
    b'\xc0hello\xc0'
    >>> encode(b'with\xc0embedded\xdbsymbols')
    b'\xc0with\xdb\xdcembedded\xdb\xddsymbols\xc0'
    >>> encode(b'with\xdb\xdcembedded\xdb\xddescaped\xdb\xdbsequence')
    b'\xc0with\xdb\xdd\xdcembedded\xdb\xdd\xddescaped\xdb\xdd\xdb\xddsequence\xc0'
    >>>
    
    '''
    return bytes(_END + data.replace(_ESC, _ESC_ESC).replace(_END, _ESC_END) + _END)
    
def decode(packet):
    '''decode(packet) -> bytes object representing the decoded SLIP packet
    
    Packet must be in format <END> <escaped-data> <END>
    Missing leading or trailing <END> symbols are allowed,
    as are multiple occurances of the <END> symbol.
    
    >>> decode(b'\xc0hello\xc0')
    b'hello'
    >>> decode(b'\xc0with\xdb\xdcembedded\xdb\xddsymbols\xc0')
    b'with\xc0embedded\xdbsymbols'
    >>> decode(b'\xc0with\xdb\xdd\xdcembedded\xdb\xdd\xddescaped\xdb\xdd\xdb\xddsequence\xc0')
    b'with\xdb\xdcembedded\xdb\xddescaped\xdb\xdbsequence'
    >>> 

    '''
    return bytes(packet.strip(_END).replace(_ESC_END, _END).replace(_ESC_ESC, _ESC))


class _Buffer:
    '''Class _Buffer buffers data until a complete SLIP packet has been received.'''
    
    def __init__(self, read_func, *read_func_args):
        '''_Buffer(read_func, *read_func_args) --> Initialize _Buffer
        
        read_func is a function that will be called to fetch data.
        read_func_args is a tuple with arguments that will be passed to read_func.
        '''
        self.reset()
        self.read_func = read_func
        self.read_func_args = read_func_args
    
    def reset(self, pos=0):
        '''reset(pos=0) --> clear the internal buffer.
        
        The value pos is used to indicate the current read position in the data source.
        This is used when the application performs a seek on the data input.
        '''
        self.data = bytearray()     # internal buffer
        self.bytes_read = pos       # number of bytes read from the data source
        self.pos = pos              # number of bytes processed (<= bytes_read)
    
    def get(self, *args):
        '''get(*args) --> a decoded SLIP packet
        
        Data is read into the internal buffer until it contains at least one complete
        SLIP packet. This packet is then extracted and decoded, and returned to the caller.
        Any arguments provided with the call to 'get' are passed to the actual read function.
        '''
        
        # Read data until there is at least one non-<END> byte.
        while set(self.data) <= set(_END):
            b = self.read_func(*(self.read_func_args + args))
            if len(b) == 0:
                raise EOFError()
            self.data.extend(b)
            self.bytes_read += len(b)

        # Remove any leading <END> bytes
        buf_len = len(self.data)
        self.data = self.data.lstrip(_END)
        self.pos += buf_len - len(self.data)
        
        # Read data until the delimiting <END> symbol is in the buffer
        while _END not in self.data:
            b = self.read_func(*(self.read_func_args + args))
            if len(b) == 0:
                raise EOFError()
            self.data.extend(b)
            self.bytes_read += len(b)
        
        # Extract the packet from the buffer
        end_index = self.data.find(_END)
        packet = self.data[:end_index]
        del self.data[:end_index+1]
        self.pos += end_index+1
        
        return decode(packet)
    
    @property
    def unread_bytes(self):
        '''unread_bytes --> the number of bytes in the buffer that have not yet been processed'''
        return self.bytes_read - self.pos


# The original intention was to make the SLIP IO objects inherit from the
# corresponding IO classes. However, one use case for the SLIP wrappers
# for io.BufferedReader and family is to apply the SLIP protocol
# to an existing IO object, e.g. one that is returned from socket.makefile.
# Since the IO objects are coded in C, modifying the __class__ attribute is not possible.
# The only way to make this happen is to detach the raw stream from the IO object,
# and use that for the initialization of the SLIP IO object.
# Unfortunately, it is not possible to detach the raw streams from an BufferedRWPair
# object.
# For this reason the SLIP IO objects contain their corresponding BufferedIO objects
# (has-a relation in stead of is-a). This has the disadvantage that In order to treat
# the SLIP IO objects as BufferedIO objects, all methods and attribute lookups must be
# explicitly passed to the contained BufferedIO object.

class _slipfuncs:
    '''_slipfuncs provides the common BufferedIO methods and attributes'''
    
    def __init__(self, *args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], io.BufferedIOBase):
            # The object is initialized with a BufferedIO object. 
            self._io = args[0]
        else:
            # Create the proper BufferedIO object
            self._io = self.__class__._io(*args, **kwargs)
        
    def __repr__(self):
        return '<{0:s}.{1:s} object at 0x{2:08X}>'.format(self.__module__,
                                                   self.__class__.__name__,
                                                   id(self))
            
    def close(self):
        return self._io.close()
    
    @property
    def closed(self):
        return self._io.closed
    
    def fileno(self):
        return self._io.fileno()
    
    def isatty(self):
        return self._io.isatty()
    
    def readable(self):
        return self._io.readable()
    
    def seek(self, offset, whence=io.SEEK_SET):
        return self._io.seek(offset, whence)
    
    def seekable(self):
        return self._io.seekable()
    
    def tell(self):
        return self._io.tell()
    
    def writable(self):
        return self._io.writable()
    
    @property
    def raw(self):
        return self._io.raw
    
    def detach(self):
        return self._io.detach()
    
    
class _slipreaderfuncs(_slipfuncs):
    '''_slipreaderfuncs provides the BufferedIO functions that are specific for readable objects'''
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create the internal buffer that will use the read1 method of the underlying BufferedIO object
        self._buffer = _Buffer(self._io.read1, io.DEFAULT_BUFFER_SIZE)
        
    def read(self):
        '''read() --> the next decoded SLIP packet'''
        return self._buffer.get()
    
    readline = read
    read1 = read
    
    def readlines(self, hint=-1):
        '''readlines(hint=-1) -> list with at most hint slip-decoded packets.
        
        Will return a list with all packets if hint is negative.'''
        if hint < 0:
            return list(self)
        out = []
        try:
            for _ in range(hint):
                out.append(self.read())
        except EOFError:
            pass
        return out
        
    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_CUR:
            offset -= self._buffer.unread_bytes
        self._io.seek(offset, whence)
        pos = self._io.tell()
        self._buffer.reset(pos)
    
    def tell(self):
        return self._buffer.pos
    
    def __iter__(self):
        return self
    
    def __next__(self):
        try:
            return self.read()
        except EOFError:
            raise StopIteration

    def readinto(self, buf):
        '''SlipReader.readinto is not implemented.
        
        Using readinto to fill a buffer with possibly a partial or multiple SLIP packets
        is meaningless, because the separation between SLIP packets would be lost.'''
        raise io.UnsupportedOperation('readinto')
    
    def peek(self, count):
        '''SlipReader.peek is not implemented.
        
        Partial decoding and maintaining the proper position in the buffer was considered
        too much effort. It is simpler to just read the next packet, and provide your own
        buffering if needed.'''
        raise io.UnsupportedOperation('peek')

class _slipwriterfuncs(_slipfuncs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def flush(self):
        return self._io.flush()
    
    def write(self, data):
        '''write(data) --> write a SLIP packet to the underlying IO stream
        
        The SLIP packet contains the encoded data.
        '''
        self._io.write(encode(data))

    def writelines(self, lst):
        '''writelines(lst) --> write SLIP packets for each entry in lst.
        
        Each entry in lst is encoded and written to the underlying IO stream
        '''
        for i in lst:
            self.write(i)
            
    def truncate(self, size=None):
        return self._io.truncate(size)
        

class SlipReader(_slipreaderfuncs):
    _io = io.BufferedReader
    

class SlipWriter(_slipwriterfuncs):
    _io = io.BufferedWriter


class SlipRandom(_slipreaderfuncs, _slipwriterfuncs):
    _io = io.BufferedRandom


class SlipRWPair(_slipreaderfuncs, _slipwriterfuncs):
    _io = io.BufferedRWPair
    

def wrap(obj):
    '''wrap(obj) --> a SLIP IO object that wraps obj
    
    obj must be a BufferedIOBase object'''
    if not obj.readable():
        return SlipWriter(obj)  # Only SlipWriter is not readable
    if not obj.writable():
        return SlipReader(obj)  # Only SlipReader is not writable
    if not obj.seekable():
        return SlipRWPair(obj)  # Only SlipRWPair is readable, writable, but not seekable
    return SlipRandom(obj)      # SlipRandom is readable, writable, and seekable


class SlipSocket(socket.socket):
    def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, fileno=None):
        if type != socket.SOCK_STREAM:
            raise ValueError('slipsocket.SlipSocket requires type=SOCK_STREAM')
        super().__init__(family, type, proto, fileno)
        self._buffer = _Buffer(super().recv, io.DEFAULT_BUFFER_SIZE)
    
    def accept(self):
        conn, addr = super().accept()
        # conn is a regular socket. It must be converted to a SlipSocket
        return self.__class__(conn.family, conn.type, conn.proto, conn.detach()), addr

    def makefile(self, mode='r'):
        if 'b' not in mode:
            mode += 'b'
        return wrap(super().makefile(mode))
    
    def sendall(self, data):
        super().sendall(encode(data))
    
    send = sendall
    
#    def _recv(self, flags=0):
#        # Wait until the buffer contains something different than <END> symbols
#        while set(self._buffer) <= set(_END):
#            self._refresh(flags)
#        
#        # Buffer contains at least one none <END> symbol
#        # Remove all leading <END> symbols
#        self._buffer = self._buffer.lstrip(_END)
#        
#        # Wait until the buffer contains the trailing <END> symbol
#        while _END not in self._buffer:
#            self._refresh(flags)
#        
#        # Locate the (first) trailing <END> symbol and extract the packet
#        end_index = self._buffer.find(_END)
#        packet = self._buffer[:end_index]
#        
#        # Remove the packet from the buffer, including the trailing <END> symbol
#        del self._buffer[:end_index+1]
#        
#        # Return the decoded data and source
#        return decode(packet)

    def recv(self, flags=0):
        '''recv(flags=0) --> the decoded version of the next received SLIP packet'''
        return self._buffer.get(flags)
    
    def recvfrom(self, flags=0):
        raise AttributeError('slipsocket.socket does not support recvfrom')

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
    

        
if hasattr(socket, 'socketpair'):
    def slipSocketPair(family=None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_IP):
        a, b = socket.socketpair(family, type, proto)
        a = SlipSocket(family, type, proto, a.detach())
        b = SlipSocket(family, type, proto, b.detach())
        return a, b


def slipFromFd(fd, family, type, proto=0):
    nfd = socket.dup(fd)
    return SlipSocket(family, type, proto, nfd)

def createSlipConnection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect to *address* and return the SlipSocket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used.  If *source_address* is set it must be a tuple of (host, port)
    for the socket to bind as a source address before making the connection.
    An host of '' or port 0 tells the OS to use the default.
    """
    sock = socket.create_connection(address, timeout, source_address)
    return SlipSocket(sock.family, sock.type, sock.proto, sock.detach())


