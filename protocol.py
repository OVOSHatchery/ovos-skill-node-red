from os.path import exists, dirname
from threading import Thread
import os
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory

from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.messagebus.message import Message
from mycroft.util.log import LOG as logger

from util import create_self_signed_cert
from database.nodered import NodeDatabase

author = "jarbas"

NAME = "NodeRed-Mycroft"


def root_dir():
    """ Returns root directory for this project """
    return os.path.dirname(os.path.realpath(__file__ + '/.'))

nodes = NodeDatabase()


# protocol
class NodeRedProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        logger.info("Client connecting: {0}".format(request.peer))
        # validate user
        api = request.headers.get("api")
        ip = request.peer.split(":")[1]
        context = {"source": self.peer}
        self.platform = request.headers.get("platform", "unknown")
        user = nodes.get_node_by_api_key(api)
        if not user:
            logger.info("Node_red provided an invalid api key")
            self.factory.emitter_send("node_red.connection.error",
                                      {"error": "invalid api key",
                                       "peer": request.peer,
                                       "api_key": api},
                                      context)
            raise ValueError("Invalid API key")
        # send message to internal mycroft bus
        data = {"peer": request.peer, "headers": request.headers}
        self.factory.emitter_send("node_red.connect", data, context)
        # return a pair with WS protocol spoken (or None for any) and
        # custom headers to send in initial WS opening handshake HTTP response
        headers = {"source": NAME}
        return (None, headers)

    def onOpen(self):
        """
       Connection from client is opened. Fires after opening
       websockets handshake has been completed and we can send
       and receive messages.

       Register client in factory, so that it is able to track it.
       """
        self.factory.register_client(self, self.platform)
        logger.info("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        if isBinary:
            logger.info("Binary message received: {0} bytes".format(len(payload)))
        else:
            logger.info("Text message received: {0}".format(payload.decode('utf8')))

        self.factory.process_message(self, payload, isBinary)

    def onClose(self, wasClean, code, reason):
        self.factory.unregister_client(self, reason=u"connection closed")
        logger.info("WebSocket connection closed: {0}".format(reason))
        ip = self.peer.split(":")[1]
        data = {"peer": self.peer, "code": code, "reason": "connection closed", "wasClean": wasClean}
        context = {"source": self.peer}
        self.factory.emitter_send("node_red.disconnect", data, context)

    def connectionLost(self, reason):
        """
       Client lost connection, either disconnected or some error.
       Remove client from list of tracked connections.
       """
        self.factory.unregister_client(self, reason=u"connection lost")
        logger.info("WebSocket connection lost: {0}".format(reason))
        ip = self.peer.split(":")[1]
        data = {"peer": self.peer, "reason": "connection lost"}
        context = {"source": self.peer}
        self.factory.emitter_send("node_red.disconnect", data, context)


# socket internals
class NodeRedFactory(WebSocketServerFactory):
    def __init__(self, *args, **kwargs):
        super(NodeRedFactory, self).__init__(*args, **kwargs)
        # list of connected clients
        self.clients = {}
        # ip block policy
        self.ip_list = []
        self.blacklist = True # if False, ip_list is a whitelist
        # mycroft_ws
        self.emitter = None
        self.emitter_thread = None
        self.create_internal_emitter()

    def emitter_send(self, type, data=None, context=None):
        data = data or {}
        context = context or {}
        self.emitter.emit(Message(type, data, context))

    def connect_to_internal_emitter(self):
        self.emitter.run_forever()

    def create_internal_emitter(self):
        # connect to mycroft internal websocket
        self.emitter = WebsocketClient()
        self.register_internal_messages()
        self.emitter_thread = Thread(target=self.connect_to_internal_emitter)
        self.emitter_thread.setDaemon(True)
        self.emitter_thread.start()

    def register_internal_messages(self):
        # catch all messages
        self.emitter.on('message', self.handle_message)
        self.emitter.on('node_red.send', self.handle_send)

    # websocket handlers
    def register_client(self, client, platform=None):
        """
       Add client to list of managed connections.
       """
        platform = platform or "unknown"
        logger.info("registering node_red: " + str(client.peer))
        t, ip, sock = client.peer.split(":")
        # see if ip adress is blacklisted
        if ip in self.ip_list and self.blacklist:
            logger.warning("Blacklisted ip tried to connect: " + ip)
            self.unregister_client(client, reason=u"Blacklisted ip")
            return
        # see if ip adress is whitelisted
        elif ip not in self.ip_list and not self.blacklist:
            logger.warning("Unknown ip tried to connect: " + ip)
            #  if not whitelisted kick
            self.unregister_client(client, reason=u"Unknown ip")
            return
        self.clients[client.peer] = {"object": client, "status":
            "connected", "platform": platform}
        context = {"source": client.peer}
        self.emitter.emit(
            Message("node_red.connect", {"peer": client.peer},  context))

    def unregister_client(self, client, code=3078, reason=u"unregister client request"):
        """
       Remove client from list of managed connections.
       """
        logger.info("deregistering node_red: " + str(client.peer))
        if client.peer in self.clients.keys():
            client_data = self.clients[client.peer] or {}
            j, ip, sock_num = client.peer.split(":")
            context = {"user": client_data.get("names", ["unknown_user"])[0],
                       "source": client.peer}
            self.emitter.emit(
                Message("node_red.disconnect",
                        {"reason": reason, "peer": client.peer},
                        context))
            client.sendClose(code, reason)
            self.clients.pop(client.peer)

    def process_message(self, client, payload, isBinary):
        """
       Process message from client, decide what to do internally here
       """
        logger.info("processing message from client: " + str(client.peer))
        client_data = self.clients[client.peer]
        client_protocol, ip, sock_num = client.peer.split(":")
        # TODO this would be the place to check for blacklisted
        # messages/skills/intents per node instance

        if isBinary:
            # TODO receive files
            pass
        else:
            # add context for this message
            message = Message.deserialize(payload)
            message.context["source"] = client.peer
            message.context["destinatary"] = "skills"
            message.context["platform"] = "node_red"
            # send client message to internal mycroft bus
            self.emitter.emit(message)

    # mycroft handlers
    def handle_send(self, message):
        # send message to client
        msg = message.data.get("payload")
        is_file = message.data.get("isBinary")
        peer = message.data.get("peer")
        if is_file:
            # TODO send file
            pass
        elif peer in self.clients:
            # send message to client
            client = self.clients[peer]
            payload = Message.serialize(msg)
            client.sendMessage(payload, False)
        else:
            logger.error("That client is not connected")
            self.emitter_send("node_red.send.error",
                                      {"error": "Node Red is not connected",
                                       "peer": peer},
                                      message.context)

    def handle_message(self, message):
        # forward internal messages to clients if they are the target
        message = Message.deserialize(message)
        message.context = message.context or {}
        peer = message.context.get("destinatary")
        if peer and peer in self.clients:
            client_data = self.clients[peer] or {}
            client = client_data.get("object")
            client.sendMessage(message.serialize(), False)

if __name__ == '__main__':

    # server
    host = "127.0.0.1"
    port = 6789
    adress = u"wss://" + unicode(host) + u":" + unicode(port)
    cert = root_dir() + '/certs/red.crt'
    key = root_dir() + '/certs/red.key'

    factory = NodeRedFactory(adress)
    factory.protocol = NodeRedProtocol

    if not exists(key) or not exists(cert):
        logger.warning("ssl keys dont exist, creating self signed")
        dir = dirname(__file__) + "/certs"
        name = key.split("/")[-1].replace(".key", "")
        create_self_signed_cert(dir, name)
        cert = dir + "/" + name + ".crt"
        key = dir + "/" + name + ".key"
        logger.info("key created at: " + key)
        logger.info("crt created at: " + cert)

    # SSL server context: load server key and certificate
    contextFactory = ssl.DefaultOpenSSLContextFactory(key, cert)

    reactor.listenSSL(port, factory, contextFactory)
    reactor.run()
