import time

import procbridge

delegate = procbridge.Delegate()


@delegate.api
def gettime(self, **kw):
    return time.time()


@delegate.api
def echo(self, echo, **kw):
    # time.sleep(5)
    return "Hello:" + echo


@delegate.api
def add(self, elements, conn, **kw):
    # return {'result': sum(x for x in elements)}  #long version
    for i in elements:
        self.server.write_back(conn, {'element':i})
    return sum(elements)


@delegate.api
def geterror(self, **kw):
    raise Exception("shit happened")


@delegate.api
def shutdown(self, **kw):
    self.server.stop()


if __name__ == '__main__':

    host = '127.0.0.1'
    port = 8077

    # start socket server
    server = procbridge.ProcBridgeServer(host, port, delegate)
    server.start()
    print('listening...')

    # raw_input("press any key to exit...")

    server.wait_for_stop()

    # server.stop()
    print('bye!')
