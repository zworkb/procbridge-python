import socket
import json
import threading

_STATUS_CODE_REQUEST = 0
_STATUS_CODE_GOOD_RESPONSE = 1
_STATUS_CODE_BAD_RESPONSE = 2    # protocol errors
_STATUS_CODE_ERROR_RESPONSE = 3  # app level errors

_KEY_API = 'api'
_KEY_BODY = 'body'
_KEY_MSG = 'msg'

_ERROR_MSG_MALFORMED_DATA = 'malformed data'
_ERROR_MSG_INCOMPATIBLE_VERSION = 'incompatible version'
_ERROR_MSG_INVALID_STATUS_CODE = 'invalid status code'


FLAG = 'pb'
VERSION = [1, 0]

API_CLOSE = '__PB_CLOSE__'
REQ_ID = '__REQID__'
RESP_TO = '__RESP_TO__'


class ProcServerPythonException(Exception):
    """Runtime exception"""
    def __init__(self, ex):
        self.exception = _STATUS_CODE_BAD_RESPONSE
        self.message = ex.message

    def __str__(self):
        return "ProcBridge Server Exception [Python] %s:%s" % (self.exception.__class__, self.message)


def bytes2long(buf):
    """
    converts a 32 bit int to a little endian byte array
    :param buf: bytestring
    :return:
    """
    res = ord(buf[0]) +\
          (ord(buf[1]) << 8) +\
          (ord(buf[2]) << 16) +\
          (ord(buf[3]) << 24)
    return res


def long2bytes(x):
    """
    converts a 4 byte array to a 32 bit int (little endian
    :param x: 32bit int
    :return: 4 byte array
    """
    bytes=''.join(map(chr,
              [
                  x & 255,
                  (x >> 8) & 255,
                  (x >> 16) & 255,
                  (x >> 24) & 255
              ]))
    return bytes


def _read_bytes(s, count):
    """
    reads count bytes from a socket conn
    :param s: socket connection
    :param count:
    :return: byte string
    """
    rst = b''
    while True:
        tmp = s.recv(count - len(rst))
        if len(tmp) == 0:
            break
        rst += tmp
        if len(rst) == count:
            break
    return rst


def _read_socket(s):
    """
    reads json object from a socket connection using json.reads
    :param s: socket connection
    :return: json object
    """
    # 1. FLAG 'pb'
    flag = _read_bytes(s, 2)
    if flag != b'pb':
        raise Exception(_ERROR_MSG_MALFORMED_DATA)

    # 2. VERSION
    ver = _read_bytes(s, 2)
    if ver != b'\x01\x00':
        raise Exception(_ERROR_MSG_INCOMPATIBLE_VERSION)

    # 3. STATUS CODE
    status_code = _read_bytes(s, 1)
    if len(status_code) != 1:
        raise Exception(_ERROR_MSG_MALFORMED_DATA)
    code = ord(status_code[0])

    # 4. RESERVED (2 bytes)
    reserved = _read_bytes(s, 2)
    if len(reserved) != 2:
        raise Exception(_ERROR_MSG_MALFORMED_DATA)

    # 5. LENGTH (4-byte, little endian)
    len_bytes = _read_bytes(s, 4)
    if len(len_bytes) != 4:
        raise Exception(_ERROR_MSG_MALFORMED_DATA)

    json_len = bytes2long(len_bytes)

    # 6. JSON OBJECT
    text_bytes = _read_bytes(s, json_len)
    if len(text_bytes) != json_len:
        raise Exception(_ERROR_MSG_MALFORMED_DATA)
    obj = json.loads(text_bytes, encoding='utf-8')

    return code, obj


def _write_socket(s, status_code, json_obj):
    """
    writes a json object to a socket connection
    :param s: socket conn
    :param status_code: 1: good, 2: bad, 3: app level error
    :param json_obj: what can be handled with json.dumps
    :return: None
    """
    # 1. FLAG
    s.sendall(b'pb')
    # 2. VERSION
    s.sendall(b'\x01\x00')
    # 3. STATUS CODE
    s.sendall(chr(status_code))
    # 4. RESERVED 2 BYTES
    s.sendall(b'\x00\x00')

    # 5. LENGTH (little endian)
    json_text = json.dumps(json_obj)
    json_bytes = json_text #bytes(json_text, encoding='utf-8')
    # len_bytes = len(json_bytes).to_bytes(4, byteorder='little')
    len_bytes = len(json_bytes)
    bytes_len_bytes = long2bytes(len_bytes)
    len_bytes = long2bytes(len_bytes)
    s.sendall(len_bytes)

    # 6. JSON
    s.sendall(json_bytes)


def _read_request(s):
    """
    reads request from socket, uses _read_socket
    :param s: socket conn
    :return: tuple (<procedure name>:str, {.arbitrary key/value params})
    """
    status_code, obj = _read_socket(s)
    if status_code != _STATUS_CODE_REQUEST:
        raise Exception(_ERROR_MSG_INVALID_STATUS_CODE)
    if _KEY_API not in obj:
        raise Exception(_ERROR_MSG_MALFORMED_DATA)
    if _KEY_BODY in obj:
        return str(obj[_KEY_API]), obj[_KEY_BODY]
    else:
        return str(obj[_KEY_API]), {}


def _read_response(s):
    """
    reads response from socket conn (XXX: not ready)
    :param s: socket conn
    :return: tuple (status code:int, json dict)
    """
    status_code, obj = _read_socket(s)
    if status_code == _STATUS_CODE_GOOD_RESPONSE:
        if _KEY_BODY not in obj:
            return status_code, {}
        else:
            return status_code, obj[_KEY_BODY]
    elif status_code == _STATUS_CODE_BAD_RESPONSE:
        if _KEY_MSG not in obj:
            return status_code, ''
        else:
            return status_code, str(obj[_KEY_MSG])
    else:
        raise Exception(_ERROR_MSG_INVALID_STATUS_CODE)


def _write_request(s, api, body):
    """
    writes request to socket conn XXX: not ready
    :param s: socket stream
    :param api: string
    :param body: dict that can be processed by json.dumps
    :return: None
    """
    _write_socket(s, _STATUS_CODE_REQUEST, {
        _KEY_API: api,
        _KEY_BODY: body
    })


def _write_good_response(s, json_obj, resp_to):
    """
    writes  a successful response to a socket conn
    :param s: socket conn
    :param json_obj: dict that can be processed by json.dumps
    :param resp_to: id of request being responded to
    :return: None
    """
    _write_socket(s, _STATUS_CODE_GOOD_RESPONSE, {
        _KEY_BODY: json_obj,
        RESP_TO:resp_to
    })


def _write_error_response(s, json_obj, resp_to=-1):
    """
    writes application level error to response.
    will be handled as exception on client side
    :param s: socket conn
    :param json_obj: dict that can be processed by json.dumps
    :param resp_to: id of request being responded to
    :return: None
    """
    _write_socket(s, _STATUS_CODE_ERROR_RESPONSE, {
        _KEY_MSG: json_obj,
        RESP_TO: resp_to
    })


def _write_bad_response(s, message):
    """
    passes a protocol exception
    :param s: socket conn
    :param message: string
    :return: None
    """
    _write_socket(s, _STATUS_CODE_BAD_RESPONSE, {
        _KEY_MSG: message
    })


class ProcBridge:
    """
    client end of protocol
    """

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def request(self, api, body=None) :
        if body is None:
            body = {}
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host, self.port))
        try:
            _write_request(s, api, body)
            resp_code, obj = _read_response(s)
            if resp_code == _STATUS_CODE_GOOD_RESPONSE:
                return obj
            else:
                raise Exception(obj)
        finally:
            s.close()


class ProcBridgeServer:
    """
    server side of protocol
    """

    def __init__(self, host, port, delegate):
        """
        :param host:
        :param port:
        :param delegate: server side api handler
        """
        self.host = host
        self.port = port
        self.started = False
        self.lock = threading.Lock()
        self.socket = None
        self.delegate = delegate
        self.delegate.server = self
        self.delegate.socket = self.socket

    def start(self):
        self.lock.acquire()
        try:
            if self.started:
                return

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(0)
            t = threading.Thread(target=_start_server_listener, args=(self,))
            t.start()
            self.started = True
        finally:
            self.lock.release()

    def stop(self):
        self.lock.acquire()
        try:
            if not self.started:
                return
            self.socket.close()
            self.socket = None
            self.started = False
        finally:
            self.lock.release()

    def write_back(self, conn, data):
        """
        writes back data
        :param data: a json-translatable object
        :return: None
        """
        # _write_socket(conn, _STATUS_CODE_GOOD_RESPONSE, data)
        _write_good_response(conn, data, -1)


def _start_server_listener(server):
    """
    starts server listener
    called internally by ProcBridgeServer.start()
    :param server: ProcBridgeServer instance
    :return:
    """
    try:
        while True:
            server.lock.acquire()
            if not server.started:
                return
            server.lock.release()

            # assert started == true:
            conn, _ = server.socket.accept()
            t = threading.Thread(target=_start_connection, args=(server, conn,))
            t.start()
    # except ConnectionAbortedError:
    except IOError:
        # socket stopped
        pass


class Delegate(object):
    """
    api handler, will be passed to ProcBridgeServer constructor
    usage:

    delegate = procbridge.Delegate()

    @delegate.api
    def gettime(self, **kw):
        return time.time()


    @delegate.api
    def echo(self, echo, **kw):
        time.sleep(5)
        return echo

    server = procbridge.ProcBridgeServer(host, port, delegate)
    server.start()

    """
    handlers = {}

    def __call__(self, api, kw, conn):
        meth = self.handlers[api]
        return meth(self, conn=conn, **kw)

    def api(self, f):
        """decorator for api handler functions"""
        def wrapper(self, conn, *a, **kw):
            try:
                return f(self, conn=conn, *a, **kw)
            except Exception as ex:
                raise ProcServerPythonException(ex)

        self.handlers[f.__name__] = wrapper
        return wrapper


def _start_connection(server, s):
    """
    starts handling a new connection, called by _start_server_listener
    :param server: ProcBridgeServer
    :param s: socket conn
    :return: None
    """
    try:
        while server.started:
            api, body = _read_request(s)
            print 'api:', api, body
            if api == API_CLOSE:
                print 'closing'
                break
            try:
                reply = server.delegate(api, body, conn=s)
                print 'result:', reply

                # if result is not a dict, convert it to a dict containing 'result'
                if not isinstance(reply, dict):
                    reply = {'result': reply}

                if reply is None:
                    reply = {}

                resp_to = body[REQ_ID]
                _write_good_response(s, reply, resp_to=resp_to)
            except ProcServerPythonException as ex:
                resp_to=body[REQ_ID]
                print 'resp_to:', resp_to
                _write_error_response(s, ex.message, resp_to=resp_to)
            except Exception as ex:
                _write_bad_response(s, str(ex))

    except Exception as e: #TODO: fix that seriously
        raise
    finally:
        s.close()
