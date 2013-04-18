import unittest
import doctest

import io
import socket

from unittest.case import _ExpectedFailure
#
#import socket
#import signal
#import math
#import gc
import queue
try:
    import _thread as thread
    import threading
except ImportError:
    thread = None
    threading = None

import slipsocket


#def load_tests(loader, tests, ignore):
#    tests.addTests(doctest.DocTestSuite(slipsocket))
#    return tests
#
# Test the basic encoding and decoding functions
#

class EncodingDecodingTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    def test_encoding_decoding(self):
        for decoded, encoded in self.data:
            self.assertEqual(encoded, slipsocket.encode(decoded))
            self.assertEqual(decoded, slipsocket.decode(encoded))
    
    def test_strange_encodings(self):
        for encoded, decoded in [(b'\xc0\xc0\xc0', b''),
                                 (b'\xc0\xc0\xc0text\xc0\xc0', b'text'),
                                 (b'text\xc0\xc0', b'text'),
                                 (b'\xc0\xc0\xc0text', b'text'),
                                 (b'text', b'text'),
                                 ]:
            self.assertEqual(decoded, slipsocket.decode(encoded))
        

#The type of file object returned by the open() function depends on the mode.
#When open() is used to open a file in a text mode ('w', 'r', 'wt', 'rt', etc.),
#it returns a subclass of io.TextIOBase (specifically io.TextIOWrapper).
#When used to open a file in a binary mode with buffering, the returned class
#is a subclass of io.BufferedIOBase. The exact class varies: in read binary mode,
#it returns a io.BufferedReader; in write binary and append binary modes,
#it returns a io.BufferedWriter, and in read/write mode, it returns a
#io.BufferedRandom. When buffering is disabled, the raw stream, a subclass
#of io.RawIOBase, io.FileIO, is returned.

class SlipReaderTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.sr = slipsocket.SLIPReader(io.BytesIO(b''.join(t[1] for t in self.data)))
        self.decoded = list(t[0] for t in self.data)

    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPReader)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPReader object"))
        
    def test_read(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_iter(self):
        for d, r in zip(self.decoded, self.sr):
            self.assertEqual(d, r)

    def test_readline(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.readline())
        with self.assertRaises(EOFError):
            self.sr.read()
        
    def test_readlines_all(self):
        self.assertEqual(self.decoded, list(self.sr.readlines()))
    
    def test_readlines_with_hint(self):
        self.assertEqual(self.decoded[0:3], list(self.sr.readlines(3)))
    
    def test_tell(self):
        self.assertEqual(self.sr.tell(), 0)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 7)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 18)
    
    def test_seek_rewind(self):
        self.sr.readlines(3)
        self.sr.seek(0)
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_seek_and_tell(self):
        self.sr.readlines(3)
        pos = self.sr.tell()
        d = self.sr.read()
        self.sr.seek(pos)
        self.assertEqual(d, self.sr.read())
        self.sr.seek(-10, io.SEEK_CUR)
        self.assertEqual(d[-8:], self.sr.read()) # End marker and escaped char take two extra bytes
        
    def test_readinto(self):
        buf = bytearray(20)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.readinto(buf)
        
    def test_peek(self):
        self.sr.readlines(20)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.peek(3)

class SlipReaderWrapTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.b = io.BufferedReader(io.BytesIO(b''.join(t[1] for t in self.data)))
        self.sr = slipsocket.SLIPReader(self.b)
        self.decoded = list(t[0] for t in self.data)

    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPReader)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPReader object"))
        
    def test_read(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_iter(self):
        for d, r in zip(self.decoded, self.sr):
            self.assertEqual(d, r)

    def test_readline(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.readline())
        with self.assertRaises(EOFError):
            self.sr.read()
        
    def test_readlines_all(self):
        self.assertEqual(self.decoded, list(self.sr.readlines()))
    
    def test_readlines_with_hint(self):
        self.assertEqual(self.decoded[0:3], list(self.sr.readlines(3)))
    
    def test_tell(self):
        self.assertEqual(self.sr.tell(), 0)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 7)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 18)
    
    def test_seek_rewind(self):
        self.sr.readlines(20)
        self.sr.seek(0)
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_seek_and_tell(self):
        self.sr.readlines(3)
        pos = self.sr.tell()
        d = self.sr.read()
        self.sr.seek(pos)
        self.assertEqual(d, self.sr.read())
        self.sr.seek(-10, io.SEEK_CUR)
        self.assertEqual(d[-8:], self.sr.read()) # End marker and escaped char take two extra bytes
        
    def test_readinto(self):
        buf = bytearray(3)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.readinto(buf)
        
    def test_peek(self):
        self.sr.readlines(3)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.peek(3)
        
        
class SlipWriterTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw = io.BytesIO()
        self.sw = slipsocket.SLIPWriter(self.raw)
        self.decoded = list(t[0] for t in self.data)
        
    def test_inheritance(self):
        self.assertIsInstance(self.sw, slipsocket.SLIPWriter)
        
    def test_repr(self):
        self.assertTrue(repr(self.sw).startswith("<slipsocket.SLIPWriter object"))
        
    def test_write(self):
        for d in self.decoded:
            self.sw.write(d)
        self.sw.flush()
        self.assertEqual(self.buffer, self.raw.getvalue())
    
    def test_flush(self):
        out = bytearray()
        for d in self.decoded:
            out.extend(slipsocket.encode(d))
            self.sw.write(d)
            self.sw.flush()
            self.assertEqual(out, self.raw.getvalue())
    
    def test_writelines(self):
        self.sw.writelines(self.decoded)
        self.sw.flush()
        self.assertEqual(self.buffer, self.raw.getvalue())
        

class SlipWriterWrapTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw = io.BytesIO()
        self.b = io.BufferedWriter(self.raw)
        self.sw = slipsocket.SLIPWriter(self.b)
        self.decoded = list(t[0] for t in self.data)
        
    def test_inheritance(self):
        self.assertIsInstance(self.sw, slipsocket.SLIPWriter)
        
    def test_repr(self):
        self.assertTrue(repr(self.sw).startswith("<slipsocket.SLIPWriter object"))
        
    def test_write(self):
        for d in self.decoded:
            self.sw.write(d)
        self.sw.flush()
        self.assertEqual(self.buffer, self.raw.getvalue())
    
    def test_flush(self):
        out = bytearray()
        for d in self.decoded:
            out.extend(slipsocket.encode(d))
            self.sw.write(d)
            self.sw.flush()
            self.assertEqual(out, self.raw.getvalue())
    
    def test_writelines(self):
        self.sw.writelines(self.decoded)
        self.sw.flush()
        self.assertEqual(self.buffer, self.raw.getvalue())


class SlipRandomTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw = io.BytesIO()
        self.sr = slipsocket.SLIPRandom(self.raw)
        self.decoded = list(t[0] for t in self.data)
    
    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPRandom)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPRandom object"))

    def test_read_write(self):
        for d in self.decoded:
            self.sr.write(d)
        self.sr.seek(0)
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())


class SlipRandomWrapTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw = io.BytesIO()
        self.b = io.BufferedRandom(self.raw)
        self.sr = slipsocket.SLIPRandom(self.b)
        self.decoded = list(t[0] for t in self.data)
    
    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPRandom)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPRandom object"))

    def test_read_write(self):
        for d in self.decoded:
            self.sr.write(d)
        self.sr.seek(0)
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())


class SlipRWPairTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw_in = io.BytesIO(b''.join(t[1] for t in self.data))
        self.raw_out = io.BytesIO()
        self.sr = slipsocket.SLIPRWPair(self.raw_in, self.raw_out)
        self.decoded = list(t[0] for t in self.data)
    
    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPRWPair)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPRWPair object"))
        
    def test_read(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_iter(self):
        for d, r in zip(self.decoded, self.sr):
            self.assertEqual(d, r)

    def test_readline(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.readline())
        with self.assertRaises(EOFError):
            self.sr.read()
        
    def test_readlines_all(self):
        self.assertEqual(self.decoded, list(self.sr.readlines()))
    
    def test_readlines_with_hint(self):
        self.assertEqual(self.decoded[0:3], list(self.sr.readlines(3)))
    
    def test_tell(self):
        self.assertEqual(self.sr.tell(), 0)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 7)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 18)
    
    def test_seek(self):
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.seek(0)
        
    def test_readinto(self):
        buf = bytearray(20)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.readinto(buf)
        
    def test_peek(self):
        self.sr.readlines(3)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.peek(3)
    
    def test_write(self):
        for d in self.decoded:
            self.sr.write(d)
        self.sr.flush()
        self.assertEqual(self.buffer, self.raw_out.getvalue())
    
    def test_flush(self):
        out = bytearray()
        for d in self.decoded:
            out.extend(slipsocket.encode(d))
            self.sr.write(d)
            self.sr.flush()
            self.assertEqual(out, self.raw_out.getvalue())
    
    def test_writelines(self):
        self.sr.writelines(self.decoded)
        self.sr.flush()
        self.assertEqual(self.buffer, self.raw_out.getvalue())


class SlipRWPairWrapTests(unittest.TestCase):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.buffer = b''.join(t[1] for t in self.data)
        self.raw_in = io.BytesIO(b''.join(t[1] for t in self.data))
        self.raw_out = io.BytesIO()
        self.b = io.BufferedRWPair(self.raw_in, self.raw_out)
        self.sr = slipsocket.SLIPRWPair(self.b)
        self.decoded = list(t[0] for t in self.data)
    
    def test_inheritance(self):
        self.assertIsInstance(self.sr, slipsocket.SLIPRWPair)
        
    def test_repr(self):
        self.assertTrue(repr(self.sr).startswith("<slipsocket.SLIPRWPair object"))
        
    def test_read(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.read())
        with self.assertRaises(EOFError):
            self.sr.read()

    def test_iter(self):
        for d, r in zip(self.decoded, self.sr):
            self.assertEqual(d, r)

    def test_readline(self):
        for d in self.decoded:
            self.assertEqual(d, self.sr.readline())
        with self.assertRaises(EOFError):
            self.sr.read()
        
    def test_readlines_all(self):
        self.assertEqual(self.decoded, list(self.sr.readlines()))
    
    def test_readlines_with_hint(self):
        self.assertEqual(self.decoded[0:3], list(self.sr.readlines(3)))
    
    def test_tell(self):
        self.assertEqual(self.sr.tell(), 0)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 7)
        self.sr.read()
        self.assertEqual(self.sr.tell(), 18)
    
    def test_seek(self):
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.seek(0)
        
    def test_readinto(self):
        buf = bytearray(20)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.readinto(buf)
        
    def test_peek(self):
        self.sr.readlines(20)
        with self.assertRaises(io.UnsupportedOperation):
            self.sr.peek(3)
    
    def test_write(self):
        for d in self.decoded:
            self.sr.write(d)
        self.sr.flush()
        self.assertEqual(self.buffer, self.raw_out.getvalue())
    
    def test_flush(self):
        out = bytearray()
        for d in self.decoded:
            out.extend(slipsocket.encode(d))
            self.sr.write(d)
            self.sr.flush()
            self.assertEqual(out, self.raw_out.getvalue())
    
    def test_writelines(self):
        self.sr.writelines(self.decoded)
        self.sr.flush()
        self.assertEqual(self.buffer, self.raw_out.getvalue())


class BasicSockettests(unittest.TestCase):
    def setUp(self):
        self.sock = slipsocket.SLIPSocket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(self.sock.close)
        
    def test_inheritance(self):
        self.assertIsInstance(self.sock, socket.socket)
               
    def test_repr(self):
        self.assertTrue(repr(self.sock).startswith("<slipsocket.SLIPSocket object"))


# The following classes have been shamelessly adapted from test/socket.py
class ThreadingClientServerTest(unittest.TestCase):
    """TThreadingClientServerTest

    The ThreadingClientServerTest class makes it easy to create tests
    for a threaded client/server pair. 
    
    This class defines four new fixture functions with obvious
    purposes for overriding:

        server_setUp()
        server_tearDown()
        client_setUp()
        client_tearDown()

    The standard unittest setUp and tearDown fixture functions
    are normally not overwritten in classes that subclass ThreadingClientServerTest.
    
    Any test functions within the class must define
    tests in pairs, where the test name is preceeded with a
    '_' to indicate the client portion of the test. E.g.:

        def testFoo(self):
            # Server portion

        def _testFoo(self):
            # Client portion

    Any exceptions raised by the clients during their tests
    are caught and transferred to the main thread to alert
    the testing framework.

    Note, the server setup function cannot call any blocking
    functions that rely on the client thread during setup,
    unless serverExplicitReady() is called just before
    the blocking call (such as in setting up a client/server
    connection and performing the accept() in setUp().
    """

    def serverExplicitReady(self):
        """This method allows the server to explicitly indicate that
        it wants the client thread to proceed. This is useful if the
        server is about to execute a blocking routine that is
        dependent upon the client thread during its setup routine."""
        self.server_ready.set()

    def setUp(self):
        self.server_ready = threading.Event()
        self.client_ready = threading.Event()
        self.connection_ready = threading.Event()
        self.done = threading.Event()
        self.queue = queue.Queue(1)
        self.server_crashed = False
        
        # Do some munging to start the client test.
        methodname = self.id()
        i = methodname.rfind('.')
        methodname = methodname[i+1:]
        test_method = getattr(self, '_' + methodname)
        self.client_thread = thread.start_new_thread(self.client_run, (test_method,))

        try:
            self.server_setUp()
        except:
            self.server_crashed = True
            raise
        finally:
            self.server_ready.set()
        self.client_ready.wait()
    
    def tearDown(self):
        self.server_tearDown()
        self.done.wait()
        if self.queue.qsize():
            exc = self.queue.get()
            raise exc

    def server_setUp(self):
        raise NotImplementedError("client_setUp must be implemented.")
        
    def server_tearDown(self):
        self.serv.close()
        self.serv = None

    def client_run(self, test_func):
        self.server_ready.wait()
        self.client_setUp()
        self.client_ready.set()
        if self.server_crashed:
            self.client_tearDown()
            return
        if not hasattr(test_func, '__call__'):
            raise TypeError("test_func must be a callable function")
        try:
            self.connection_ready.wait()
            test_func()
        except _ExpectedFailure:
            # We deliberately ignore expected failures
            pass
        except BaseException as e:
            self.queue.put(e)
        finally:
            self.client_tearDown()

    def client_setUp(self):
        raise NotImplementedError("client_setUp must be implemented.")

    def client_tearDown(self):
        self.done.set()
        thread.exit()


class SocketConnectedTest(ThreadingClientServerTest):
    """Socket tests for client-server connection.

    self.cli_conn is a client socket connected to the server.  The
    setUp() method guarantees that it is connected to the server.
    """
    def server_setUp(self):
        self.serv = self.server_socketclass(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.bind(('127.0.0.1', 0))
        self.port = self.serv.getsockname()[1]
        self.serv.listen(1)
        
        # Indicate explicitly we're ready for the client thread to
        # proceed and then perform the blocking call to accept
        self.serverExplicitReady()
        conn, _ = self.serv.accept()
        self.cli_conn = conn
        self.connection_ready.set()

    def server_tearDown(self):
        self.cli_conn.close()
        self.cli_conn = None
        ThreadingClientServerTest.server_tearDown(self)

    def client_setUp(self):
        self.cli = self.client_socketclass(socket.AF_INET, socket.SOCK_STREAM)
        self.cli.connect(('127.0.0.1', self.port))
        self.serv_conn = self.cli

    def client_tearDown(self):
        self.serv_conn.close()
        self.serv_conn = None
        self.cli.close()
        self.cli = None
        ThreadingClientServerTest.client_tearDown(self)



@unittest.skipUnless(thread, 'Threading required for this test.')
class BasicTCPTest(SocketConnectedTest):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.server_socketclass = slipsocket.SLIPSocket
        self.client_socketclass = slipsocket.SLIPSocket
        SocketConnectedTest.setUp(self)
        
    def test_inheritance(self):
        self.assertIsInstance(self.cli_conn, slipsocket.SLIPSocket)
    
    def _test_inheritance(self):
        self.assertIsInstance(self.serv_conn, slipsocket.SLIPSocket)
                
    def testRecv(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)

    def _testRecv(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
    
    def testLargeMsg(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg*2048, m)

    def _testLargeMsg(self):
        for msg, _ in self.data:
            self.serv_conn.sendall(msg*2048)
    
    def test_recv_into(self):
        for msg, _ in self.data:
            buf = bytearray(len(msg)-2)
            n_bytes = self.cli_conn.recv_into(buf)
            self.assertEqual(n_bytes, len(msg)-2)
            self.assertEqual(buf, msg[:-2])
    
    def _test_recv_into(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def test_recv_into_underflow(self):
        for msg, _ in self.data:
            buf = bytearray(len(msg)+2)
            n_bytes = self.cli_conn.recv_into(buf)
            self.assertEqual(n_bytes, len(msg))
            self.assertEqual(buf[:n_bytes], msg)
    
    def _test_recv_into_underflow(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def test_recv_into_specific_length(self):
        for msg, _ in self.data:
            for size in len(msg), len(msg)-2, len(msg)+2:
                buf = bytearray(size)
                n_bytes = self.cli_conn.recv_into(buf, size)
                self.assertEqual(n_bytes, min(len(msg), size))
                self.assertEqual(buf[:n_bytes], msg[:min(len(msg), size)])
    
    def _test_recv_into_specific_length(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
            self.serv_conn.send(msg)
            self.serv_conn.send(msg)
    
    def test_recvfrom(self):
        peername = self.cli.getsockname()
        for msg, _ in self.data:
            m, addr = self.cli_conn.recvfrom()
            self.assertEqual(m, msg)
            self.assertEqual(addr, peername)
    
    def _test_recvfrom(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
    
    def test_recvfrom_into(self):
        peername = self.cli.getsockname()
        for msg, _ in self.data:
            buf = bytearray(len(msg)-2)
            n_bytes, addr = self.cli_conn.recvfrom_into(buf)
            self.assertEqual(n_bytes, len(msg)-2)
            self.assertEqual(buf, msg[:-2])
            self.assertEqual(addr, peername)
    
    def _test_recvfrom_into(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def test_recvfrom_into_underflow(self):
        peername = self.cli.getsockname()
        for msg, _ in self.data:
            buf = bytearray(len(msg)+2)
            n_bytes, addr = self.cli_conn.recvfrom_into(buf)
            self.assertEqual(n_bytes, len(msg))
            self.assertEqual(buf[:n_bytes], msg)
            self.assertEqual(addr, peername)
   
    def _test_recvfrom_into_underflow(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def test_recvfrom_into_specific_length(self):
        peername = self.cli.getsockname()
        for msg, _ in self.data:
            for size in len(msg), len(msg)-2, len(msg)+2:
                buf = bytearray(size)
                n_bytes, addr = self.cli_conn.recvfrom_into(buf, size)
                self.assertEqual(n_bytes, min(len(msg), size))
                self.assertEqual(buf[:n_bytes], msg[:min(len(msg), size)])
                self.assertEqual(addr, peername)
    
    def _test_recvfrom_into_specific_length(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
            self.serv_conn.send(msg)
            self.serv_conn.send(msg)
    
    def test_twoway_communication(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)
            self.cli_conn.send(m)
    
    def _test_twoway_communication(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
            m = self.serv_conn.recv()
            self.assertEqual(msg, m)
     
    def test_makefile_readonly_implicit_binary(self):
        rf = self.cli_conn.makefile()
        self.assertIsInstance(rf, slipsocket.SLIPReader)
        for msg, _ in self.data:
            m = rf.read()
            self.assertEqual(msg, m)
    
    def _test_makefile_readonly_implicit_binary(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
            
    def testFromFd(self):
        fd = self.cli_conn.fileno()
        sock = slipsocket.slip_fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        self.assertIsInstance(sock, slipsocket.SLIPSocket)
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)

    def _testFromFd(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def testDup(self):
        sock = self.cli_conn.dup()
        self.assertIsInstance(sock, slipsocket.SLIPSocket)
        self.addCleanup(sock.close)
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)

    def _testDup(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

    def testShutdown(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)
        # wait for _testShutdown to finish: on OS X, when the server
        # closes the connection the client also becomes disconnected,
        # and the client's shutdown call will fail. (Issue #4397.)
        self.done.wait()

    def _testShutdown(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
        self.serv_conn.shutdown(2)

    def testDetach(self):
        fileno = self.cli_conn.fileno()
        f = self.cli_conn.detach()
        self.assertEqual(f, fileno)
        #  cli_conn cannot be used anymore...
        self.assertTrue(self.cli_conn._closed)
        self.assertRaises(socket.error, self.cli_conn.recv)
        self.cli_conn.close()
        # ...but we can create another socket using the (still open)
        # file descriptor
        sock = slipsocket.SLIPSocket(socket.AF_INET, socket.SOCK_STREAM, fileno=f)
        self.addCleanup(sock.close)
        self.assertIsInstance(sock, slipsocket.SLIPSocket)
        for msg, _ in self.data:
            m = sock.recv()
            self.assertEqual(msg, m)

    def _testDetach(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

class CreateConnectionTest(SocketConnectedTest):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.server_socketclass = slipsocket.SLIPSocket
        self.client_socketclass = slipsocket.SLIPSocket
        SocketConnectedTest.setUp(self)
    
    def client_setUp(self):
        self.cli = slipsocket.create_slip_connection(('127.0.0.1', self.port))
        self.serv_conn = self.cli

    def test_inheritance(self):
        self.assertIsInstance(self.cli_conn, slipsocket.SLIPSocket)
    
    def _test_inheritance(self):
        self.assertIsInstance(self.serv_conn, slipsocket.SLIPSocket)
        
    def test_communication(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)

    def _test_communication(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)
       


@unittest.skipUnless(thread, 'Threading required for this test.')
class RawSendTest(SocketConnectedTest):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.server_socketclass = slipsocket.SLIPSocket
        self.client_socketclass = socket.socket
        SocketConnectedTest.setUp(self)
        
    def test_inheritance(self):
        self.assertIsInstance(self.cli_conn, slipsocket.SLIPSocket)
    
    def _test_inheritance(self):
        self.assertIsInstance(self.serv_conn, socket.socket)
                
    def testRecv(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)

    def _testRecv(self):
        for _, raw in self.data:
            self.serv_conn.sendall(raw)

    def testBulk(self):
        for msg, _ in self.data:
            m = self.cli_conn.recv()
            self.assertEqual(msg, m)
    
    def _testBulk(self):
        self.serv_conn.sendall(b''.join(raw for _, raw in self.data))


@unittest.skipUnless(thread, 'Threading required for this test.')
class RawRecvTest(SocketConnectedTest):
    data = [(b'hallo', b'\xc0hallo\xc0'),
            (b'pre\xc0post', b'\xc0pre\xdb\xdcpost\xc0'),
            (b'pre\xdbpost', b'\xc0pre\xdb\xddpost\xc0'),
            (b'pre\xc0middle\xdbpost', b'\xc0pre\xdb\xdcmiddle\xdb\xddpost\xc0'),
            (b'pre\xdb\xdcpost', b'\xc0pre\xdb\xdd\xdcpost\xc0'),
            (b'pre\xdb\xddpost', b'\xc0pre\xdb\xdd\xddpost\xc0'),
            ]
    
    def setUp(self):
        self.server_socketclass = socket.socket
        self.client_socketclass = slipsocket.SLIPSocket
        SocketConnectedTest.setUp(self)
        
    def test_inheritance(self):
        self.assertIsInstance(self.cli_conn, socket.socket)
    
    def _test_inheritance(self):
        self.assertIsInstance(self.serv_conn, slipsocket.SLIPSocket)
                
    def test_recv(self):
        for _, raw in self.data:
            recv_count = 0
            m = bytearray()
            while recv_count < len(raw):
                b = self.cli_conn.recv(len(raw)-recv_count)
                recv_count += len(b)
                m.extend(b)
            self.assertEqual(raw, m)

    def _test_recv(self):
        for msg, _ in self.data:
            self.serv_conn.send(msg)

