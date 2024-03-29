from JumpScale import j

import tornado.ioloop
import tornado.web

from servers.serverbase import returnCodes


class MainHandlerRPC(tornado.web.RequestHandler):

    """
    processes the incoming web requests
    """

    def initialize(self, server):
        self.server = server

    def responseRaw(self,data,start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [data]

    def post(self, *args, **kwargs):
        data = self.request.body
        data = data.decode('utf-8')
        if self.request.headers.get('Content-Type', '').startswith('application/json'):
            return self.handleJSONRPC()
        else:
            category, cmd, data2, informat, returnformat, sessionid = j.servers.base._unserializeBinSend(data)
            resultcode, returnformat, result = self.server.daemon.processRPCUnSerialized(cmd, informat, returnformat, data2, sessionid, category=category)
            data3 = j.servers.base._serializeBinReturn(resultcode, returnformat, result)
            self.write(data3)
            self.flush()

    def invalidRequest(self):
        msg = {'error': {'code': -32600, 'message': 'Invalid Request'}, 'id': None, 'jsonrpc': '2.0'}
        return msg

    def handleJSONRPC(self):
        data = self.request.body
        data = data.decode('utf-8')

        payload = j.data.serializer.json.loads(data)

        try:
            method_name = payload['method']
            params = payload.get('params', dict())

            category, cmd = method_name.split('.', 1)
            sessionid = params.pop('sessionid', None)
            session = self.server.daemon.getSession(sessionid=sessionid, cmd=cmd)
            return_code, return_format, data = self.server.daemon.processRPC(cmd, params, 'j', session, category=category)
            if return_code == returnCodes.OK:
                result = {'result': data, 'id': payload['id'], 'jsonrpc': '2.0'}
            else:
                result = {'result': None, 'id': payload['id'], 'jsonrpc': '2.0', 'error': {'code': 1, 'data': data}}
        except Exception as e:
            print(e)
            result = self.invalidRequest()

        statuscode, statusmessage = (200, 'OK') if not result.get('error', None) else (500, 'Internal Server Error')
        self.set_status(statuscode, statusmessage)
        self.set_header('Content-Type', 'application/json')

        self.write(j.data.serializer.json.dumps(result))
        self.flush()

class TornadoServer():

    def __init__(self, addr, port, sslorg=None, ssluser=None, sslkeyvaluestor=None):
        """
        @param handler is passed as a class
        """
        self.port = port
        self.addr = addr
        self.key = "1234"
        self.nr = 0
        # self.jobhandler = JobHandler()
        self.daemon = j.servers.base.getDaemon(sslorg=sslorg, ssluser=ssluser, sslkeyvaluestor=sslkeyvaluestor)
        self.application = tornado.web.Application([(r"(.*)", MainHandlerRPC, dict(server=self)), ])
        self.type = "tornado"

    def start(self):
        print(("started on %s" % self.port))
        self.application.listen(self.port)

        self.ioloop = tornado.ioloop.IOLoop.instance()
        self.ioloop.start()

    def addCMDsInterface(self, MyCommands, category=""):
        self.daemon.addCMDsInterface(MyCommands, category)

    def _stack_context_handle_exception(self, *kwargs):
        print(kwargs)
        
