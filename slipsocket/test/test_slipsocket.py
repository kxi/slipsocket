import unittest
from unittest.case import _ExpectedFailure

import socket
import signal
import math
import gc
import queue
try:
    import _thread as thread
    import threading
except ImportError:
    thread = None
    threading = None

import slipsocket

#############################################################################
#
# The following code has been copied from test/support.py
#
#############################################################################

class TestFailed(Exception):
    """Test failed."""

HOST = 'localhost'

#############################################################################
#
# Test basic socket functionality
#
# The following tests are based on the standard regression tests in the
# test/test_socket module. Only the tests that involve functionality that
# is different from standard socket functionality are included here.
#
#############################################################################

class BasicTests(unittest.TestCase):
    
    def test_inheritance(self):
        s = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(s.close)
        self.assertIsInstance(s, socket)
        
    def test_repr(self):
        s = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(s.close)
        self.assertTrue(repr(s).startswith("<slipsocket.socket object"))

    def testSendAfterClose(self):
        # testing send() after close() with timeout
        sock = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.close()
        self.assertRaises(socket.error, sock.send, b"spam")

    def check_sendall_interrupted(self, with_timeout):
        # socketpair() is not stricly required, but it makes things easier.
        if not hasattr(signal, 'alarm') or not hasattr(slipsocket, 'socketpair'):
            self.skipTest("signal.alarm and slipsocket.socketpair required for this test")
        # Our signal handlers clobber the C errno by calling a math function
        # with an invalid domain value.
        def ok_handler(*args):
            self.assertRaises(ValueError, math.acosh, 0)
        def raising_handler(*args):
            self.assertRaises(ValueError, math.acosh, 0)
            1 // 0
        c, s = slipsocket.socketpair()
        old_alarm = signal.signal(signal.SIGALRM, raising_handler)
        try:
            if with_timeout:
                # Just above the one second minimum for signal.alarm
                c.settimeout(1.5)
            with self.assertRaises(ZeroDivisionError):
                signal.alarm(1)
                c.sendall(b"x" * (1024**2))
            if with_timeout:
                signal.signal(signal.SIGALRM, ok_handler)
                signal.alarm(1)
                self.assertRaises(socket.timeout, c.sendall, b"x" * (1024**2))
        finally:
            signal.signal(signal.SIGALRM, old_alarm)
            c.close()
            s.close()

    def test_sendall_interrupted(self):
        self.check_sendall_interrupted(False)

    def test_sendall_interrupted_with_timeout(self):
        self.check_sendall_interrupted(True)

    def test_dealloc_warn(self):
        sock = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM)
        r = repr(sock)
        with self.assertWarns(ResourceWarning) as cm:
            sock = None
            gc.collect()
        self.assertIn(r, str(cm.warning.args[0]))
        # An open socket file object gets dereferenced after the socket
        sock = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM)
        f = sock.makefile('rb')
        r = repr(sock)
        sock = None
        gc.collect()
        with self.assertWarns(ResourceWarning):
            f = None
            gc.collect()

    def test_name_closed_socketio(self):
        with slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            fp = sock.makefile("rb")
            fp.close()
            self.assertEqual(repr(fp), "<_io.BufferedReader name=-1>")


#############################################################################
#
# Test communication
#
# The following classes are copied and adapted from the test/test_socket.py
# module. Together they allow test cases to define a server and client in
# separate threads, and test the communication between them.
#
#############################################################################

class SocketTCPTest(unittest.TestCase):
    def init(self, server_socketclass=socket):
        self.server_socketclass = server_socketclass
        unittest.TestCase.__init__()
        
    def setUp(self):
        self.serv = self.server_socketclass(socket.AF_INET, socket.SOCK_STREAM)
        self.serv.bind((HOST, 0))
        self.port = self.serv.getsockname()[1]
        self.serv.listen(1)

    def tearDown(self):
        self.serv.close()
        self.serv = None


class ThreadableTest:
    """Threadable Test class

    The ThreadableTest class makes it easy to create a threaded
    client/server pair from an existing unit test. To create a
    new threaded class from an existing unit test, use multiple
    inheritance:

        class NewClass (OldClass, ThreadableTest):
            pass

    This class defines two new fixture functions with obvious
    purposes for overriding:

        clientSetUp ()
        clientTearDown ()

    Any new test functions within the class must then define
    tests in pairs, where the test name is preceeded with a
    '_' to indicate the client portion of the test. Ex:

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

    def __init__(self):
        # Swap the true setup function
        self.__setUp = self.setUp
        self.__tearDown = self.tearDown
        self.setUp = self._setUp
        self.tearDown = self._tearDown

    def serverExplicitReady(self):
        """This method allows the server to explicitly indicate that
        it wants the client thread to proceed. This is useful if the
        server is about to execute a blocking routine that is
        dependent upon the client thread during its setup routine."""
        self.server_ready.set()

    def _setUp(self):
        self.server_ready = threading.Event()
        self.client_ready = threading.Event()
        self.done = threading.Event()
        self.queue = queue.Queue(1)
        self.server_crashed = False

        # Do some munging to start the client test.
        methodname = self.id()
        i = methodname.rfind('.')
        methodname = methodname[i+1:]
        test_method = getattr(self, '_' + methodname)
        self.client_thread = thread.start_new_thread(
            self.clientRun, (test_method,))

        try:
            self.__setUp()
        except:
            self.server_crashed = True
            raise
        finally:
            self.server_ready.set()
        self.client_ready.wait()

    def _tearDown(self):
        self.__tearDown()
        self.done.wait()

        if self.queue.qsize():
            exc = self.queue.get()
            raise exc

    def clientRun(self, test_func):
        self.server_ready.wait()
        self.clientSetUp()
        self.client_ready.set()
        if self.server_crashed:
            self.clientTearDown()
            return
        if not hasattr(test_func, '__call__'):
            raise TypeError("test_func must be a callable function")
        try:
            test_func()
        except _ExpectedFailure:
            # We deliberately ignore expected failures
            pass
        except BaseException as e:
            self.queue.put(e)
        finally:
            self.clientTearDown()

    def clientSetUp(self):
        raise NotImplementedError("clientSetUp must be implemented.")

    def clientTearDown(self):
        self.done.set()
        thread.exit()


class ThreadedTCPSocketTest(SocketTCPTest, ThreadableTest):
    def __init__(self, server_socketclass=slipsocket.socket, client_socketclass=slipsocket.socket):
        self.client_socketclass = client_socketclass
        SocketTCPTest.__init__(self, server_socketclass)
        ThreadableTest.__init__(self)

    def clientSetUp(self):
        self.cli = self.client_socketclass(socket.AF_INET, socket.SOCK_STREAM)

    def clientTearDown(self):
        self.cli.close()
        self.cli = None
        ThreadableTest.clientTearDown(self)


class SocketConnectedTest(ThreadedTCPSocketTest):
    """Socket tests for client-server connection.

    self.cli_conn is a client socket connected to the server.  The
    setUp() method guarantees that it is connected to the server.
    """

    def setUp(self):
        ThreadedTCPSocketTest.setUp(self)
        # Indicate explicitly we're ready for the client thread to
        # proceed and then perform the blocking call to accept
        self.serverExplicitReady()
        conn, addr = self.serv.accept()
        self.cli_conn = conn

    def tearDown(self):
        self.cli_conn.close()
        self.cli_conn = None
        ThreadedTCPSocketTest.tearDown(self)

    def clientSetUp(self):
        ThreadedTCPSocketTest.clientSetUp(self)
        self.cli.connect((HOST, self.port))
        self.serv_conn = self.cli

    def clientTearDown(self):
        self.serv_conn.close()
        self.serv_conn = None
        ThreadedTCPSocketTest.clientTearDown(self)


#############################################################################
#
# Test communication
#
# The following tests are based on the standard regression tests in the
# test/test_socket module. Only the tests that involve functionality that
# is different from standard socket functionality are included here.
#
#############################################################################

@unittest.skipUnless(thread, 'Threading required for this test.')
class BasicTCPTest(SocketConnectedTest):
    msg = (b'abc\u1234\r\n' + slipsocket._END + b'a'+ slipsocket._ESC + b'b' +
           slipsocket._ESC_END + b'c' + slipsocket._ESC_ESC + b'd' +
           2*slipsocket._END + b'e' + 2*slipsocket._ESC + b'f' +
           2*slipsocket._ESC_END + b'g' + 2*slipsocket._ESC_ESC + b'h' +
           slipsocket._END + slipsocket._ESC + b'i' + slipsocket._END + slipsocket._ESC_END +
           b'j' + slipsocket._END + slipsocket._ESC_ESC + b'k' +
           slipsocket._ESC + slipsocket._END + b'l' + slipsocket._ESC + slipsocket._ESC_END +
           b'm' + slipsocket._ESC + slipsocket._ESC_ESC + b'n' +
           slipsocket._ESC_END + slipsocket._END + b'o' + slipsocket._ESC_END + slipsocket._ESC +
           b'p' + slipsocket._ESC_END + slipsocket._ESC_ESC + b'q' + slipsocket._ESC_ESC + slipsocket._END +
           b'r' + slipsocket._ESC_ESC + slipsocket._END + b's' + 
           slipsocket._ESC_ESC + slipsocket._ESC + b't' + slipsocket._ESC_ESC + slipsocket._ESC_END + b'\r\n')

    def __init__(self):
        SocketConnectedTest.__init__(self, slipsocket.socket, slipsocket.socket)

    def test_inheritance(self):
        self.assertIsInstance(self.cli_conn, slipsocket.socket)
        self.assertIsInstance(self.serv_conn, slipsocket.socket)
        
    def testRecv(self):
        # Testing large receive over TCP
        m = self.cli_conn.recv()
        self.assertEqual(self.msg, m)

    def _testRecv(self):
        self.serv_conn.send(self.msg)

    def testRecvFrom(self):
        # Testing large recvfrom() over TCP
        m, addr = self.cli_conn.recvfrom()
        self.assertEqual(self.msg, m)

    def _testRecvFrom(self):
        self.serv_conn.send(self.msg)

    def testSendAll(self):
        # Testing sendall() with a 2048 byte string over TCP
        m = self.cli_conn.recv()
        self.assertEqual(m, self.msg + b'f'* 2048)

    def _testSendAll(self):
        self.serv_conn.sendall(self.msg + b'f'*2048)

    def testFromFd(self):
        # Testing fromfd()
        fd = self.cli_conn.fileno()
        sock = slipsocket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        self.assertIsInstance(sock, slipsocket.socket)
        m = sock.recv()
        self.assertEqual(self.msg, m)

    def _testFromFd(self):
        self.serv_conn.send(self.msg)

    def testDup(self):
        # Testing dup()
        sock = self.cli_conn.dup()
        self.assertIsInstance(sock, slipsocket.socket)
        self.addCleanup(sock.close)
        m = sock.recv()
        self.assertEqual(self.msg, m)

    def _testDup(self):
        self.serv_conn.send(self.msg)

    def testShutdown(self):
        # Testing shutdown()
        m = self.cli_conn.recv()
        self.assertEqual(self.msg, m)
        # wait for _testShutdown to finish: on OS X, when the server
        # closes the connection the client also becomes disconnected,
        # and the client's shutdown call will fail. (Issue #4397.)
        self.done.wait()

    def _testShutdown(self):
        self.serv_conn.send(self.msg)
        self.serv_conn.shutdown(2)

    def testDetach(self):
        # Testing detach()
        fileno = self.cli_conn.fileno()
        f = self.cli_conn.detach()
        self.assertEqual(f, fileno)
        # cli_conn cannot be used anymore...
        self.assertTrue(self.cli_conn._closed)
        self.assertRaises(socket.error, self.cli_conn.recv)
        self.cli_conn.close()
        # ...but we can create another socket using the (still open)
        # file descriptor
        sock = slipsocket.socket(socket.AF_INET, socket.SOCK_STREAM, fileno=f)
        self.addCleanup(sock.close)
        m = sock.recv()
        self.assertEqual(self.msg, m)

    def _testDetach(self):
        self.serv_conn.send(self.msg)

