# ProcBridge for Python

ProcBridge is a lightweight socket-based IPC (Inter-Process Communication) protocol,
and it uses UTF-8 JSON text to encodes requests and responses.
Currently we have Java and Python implementations for ProcBridge.

this product is a fork of the existing but no more maintained [Project](https://github.com/gongzhang/procbridge).

Additionally the python part has been extracted into a seperate project
in order to be installed using pip

Example usage for a server:

    import procbridge

    delegate = procbridge.Delegate()

    @delegate.api
    def echo(self, echo, **kw):
        return "Hello:" + echo

    if __name__ == '__main__':

        host = '127.0.0.1'
        port = 8077

        # start socket server
        server = procbridge.ProcBridgeServer(host, port, delegate)
        server.start()
        print('listening...')

        raw_input("press any key to exit...")

        server.stop()
        print('bye!')



