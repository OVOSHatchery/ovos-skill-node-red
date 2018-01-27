# NO LICENSE 2018
#
# Unless required by applicable law or agreed to in writing, software
# distributed under this lack of License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.

from OpenSSL import crypto
from socket import gethostname
from os import makedirs
import random
from os.path import join, exists
from threading import Thread
from multiprocessing import Process
import os
import time
import base64
from twisted.internet import reactor, ssl
from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory
from autobahn.websocket.types import ConnectionDeny

from mycroft.messagebus.client.ws import WebsocketClient
from mycroft.messagebus.message import Message
from mycroft.skills.core import FallbackSkill
from mycroft.util.log import LOG

__author__ = "jarbas"

NAME = "NodeRed-Mycroft"


class NodeRedSkill(FallbackSkill):
    def __init__(self):
        super(NodeRedSkill, self).__init__()
        if "host" not in self.settings:
            self.settings["host"] = "127.0.0.1"
        if "port" not in self.settings:
            self.settings["port"] = 6789
        if "cert" not in self.settings:
            self.settings["cert"] = self._dir + '/certs/red.crt'
        if "key" not in self.settings:
            self.settings["key"] = self._dir + '/certs/red.key'
        if "timeout" not in self.settings:
            self.settings["timeout"] = 10
        if "ssl" not in self.settings:
            self.settings["ssl"] = True
        if "secret" not in self.settings:
            self.settings["secret"] = "test_key"
        if "ip_list" not in self.settings:
            self.settings["ip_list"] = []
        if "ip_blacklist" not in self.settings:
            self.settings["ip_blacklist"] = True
        self.waiting = False
        self.factory = None

    def initialize(self):
        self.settings["ssl"] = False
        prot = "wss" if self.settings["ssl"] else "ws"
        self.address = unicode(prot) + u"://" + \
                       unicode(self.settings["host"]) + u":" + \
                       unicode(self.settings["port"])

        self.node_thread = Process(target=self.connect_to_node)
        self.node_thread.start()

        LOG.info("Listening for node red connections on " + self.address)

        self.emitter.on("speak", self.handle_node_answer)
        self.emitter.on("node_red.intent_failure", self.handle_node_failure)
        self.register_fallback(self.handle_fallback, 99)
        self.register_intent_file("pingnode.intent", self.handle_ping_node)

    def connect_to_node(self):
        self.factory = NodeRedFactory(self.address)
        self.factory.protocol = NodeRedProtocol
        self.factory.ip_list = self.settings["ip_list"]
        self.factory.blacklist = self.settings["ip_blacklist"]
        if self.settings["ssl"]:
            if not exists(self.settings["key"]) or not exists(
                    self.settings["cert"]):
                LOG.warning("ssl keys dont exist, creating self signed")
                dir = self._dir + "/certs"
                name = self.settings["key"].split("/")[-1].replace(".key", "")
                create_self_signed_cert(dir, name)
                cert = dir + "/" + name + ".crt"
                key = dir + "/" + name + ".key"
                LOG.info("key created at: " + key)
                LOG.info("crt created at: " + cert)

            # SSL server context: load server key and certificate
            contextFactory = ssl.DefaultOpenSSLContextFactory(self.settings["key"],
                                                              self.settings["cert"])

            reactor.listenSSL(self.settings["port"],
                              self.factory,
                              contextFactory)
        else:
            reactor.listenTCP(self.settings["port"], self.factory)
        reactor.run()

    @property
    def node(self):
        if self.factory is None or not len(self.factory.clients.keys()):
            return None
        return self.factory.clients.keys()[0]

    def handle_node_answer(self, message):
        ''' node answered us, signal end of fallback '''
        destinatary = message.context.get("destinatary", "")
        if destinatary == "node_fallback" and self.waiting:
            self.waiting = False
            self.success = True

    def handle_node_failure(self, message):
        ''' node answered us, signal end of fallback '''
        self.waiting = False
        self.success = False

    def wait(self):
        start = time.time()
        self.waiting = True
        while self.waiting and time.time() - start < self.settings["timeout"]:
            time.sleep(0.3)

    def handle_fallback(self, message):
        # ask node
        self.success = False
        self.emitter.emit(Message("node_red.send",
                                  {"payload": {"type": "node_red.ask",
                                               "data": message.data,
                                               "context": message.context},
                                   "peer": self.node, "isBinary": False}))

        self.wait()
        return self.success

    def handle_ping_node(self, message):
        self.emitter.emit(Message("node_red.send",
                                  {"payload": {"type": "node_red.ask",
                                               "data": {"utterance", "hello"},
                                               "context": message.context},
                                   "peer": self.node, "isBinary": False}))

    def shutdown(self):
        self.node_thread.join()
        reactor.stop()
        super(NodeRedSkill, self).shutdown()


def create_skill():
    return NodeRedSkill()


# utils
def root_dir():
    """ Returns root directory for this project """
    return os.path.dirname(os.path.realpath(__file__ + '/.'))


def create_self_signed_cert(cert_dir, name="mycroft_NodeRed"):
    """
    If name.crt and name.key don't exist in cert_dir, create a new
    self-signed cert and key pair and write them into that directory.
    """

    CERT_FILE = name + ".crt"
    KEY_FILE = name + ".key"
    cert_path = join(cert_dir, CERT_FILE)
    key_path = join(cert_dir, KEY_FILE)

    if not exists(join(cert_dir, CERT_FILE)) \
            or not exists(join(cert_dir, KEY_FILE)):
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 1024)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "PT"
        cert.get_subject().ST = "Europe"
        cert.get_subject().L = "Mountains"
        cert.get_subject().O = "Jarbas AI"
        cert.get_subject().OU = "Powered by Mycroft-Core"
        cert.get_subject().CN = gethostname()
        cert.set_serial_number(random.randint(0, 2000))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha1')
        if not exists(cert_dir):
            makedirs(cert_dir)
        open(cert_path, "wt").write(
            crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        open(join(cert_dir, KEY_FILE), "wt").write(
            crypto.dump_privatekey(crypto.FILETYPE_PEM, k))

    return cert_path, key_path


# protocol
class NodeRedProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        LOG.info("Client connecting: {0}".format(request.peer))
        # validate user
        usernamePasswordEncoded = request.headers.get("authorization")
        usernamePasswordEncoded = usernamePasswordEncoded.split()
        usernamePasswordDecoded = base64.b64decode(usernamePasswordEncoded[1])
        username, api = usernamePasswordDecoded.split(":")
        context = {"source": self.peer}
        self.platform = "node_red"
        # send message to internal mycroft bus
        data = {"peer": request.peer, "headers": request.headers}
        self.factory.emitter_send("node_red.connect", data, context)

        if api != self.settings["secret"]:
            LOG.info("Node_red provided an invalid api key")
            self.factory.emitter_send("node_red.connection.error",
                                      {"error": "invalid api key",
                                       "peer": request.peer,
                                       "api_key": api},
                                      context)
            raise ConnectionDeny(4000, "Invalid API key")

    def onOpen(self):
        """
       Connection from client is opened. Fires after opening
       websockets handshake has been completed and we can send
       and receive messages.

       Register client in factory, so that it is able to track it.
       """
        LOG.info("WebSocket connection open.")
        self.factory.register_client(self, self.platform)

    def onMessage(self, payload, isBinary):
        if isBinary:
            LOG.info(
                "Binary message received: {0} bytes".format(len(payload)))
        else:
            LOG.info(
                "Text message received: {0}".format(payload.decode('utf8')))

        self.factory.process_message(self, payload, isBinary)

    def onClose(self, wasClean, code, reason):
        self.factory.unregister_client(self, reason=u"connection closed")
        LOG.info("WebSocket connection closed: {0}".format(reason))
        data = {"peer": self.peer, "code": code,
                "reason": "connection closed", "wasClean": wasClean}
        context = {"source": self.peer}
        self.factory.emitter_send("node_red.disconnect", data, context)

    def connectionLost(self, reason):
        """
       Client lost connection, either disconnected or some error.
       Remove client from list of tracked connections.
       """
        self.factory.unregister_client(self, reason=u"connection lost")
        LOG.info("WebSocket connection lost: {0}".format(reason))
        data = {"peer": self.peer, "reason": "connection lost"}
        context = {"source": self.peer}
        self.factory.emitter_send("node_red.disconnect", data, context)


# websocket connection factory
class NodeRedFactory(WebSocketServerFactory):
    def __init__(self, *args, **kwargs):
        super(NodeRedFactory, self).__init__(*args, **kwargs)
        # list of connected clients
        self.clients = {}
        # ip block policy
        self.ip_list = []
        self.blacklist = True  # if False, ip_list is a whitelist
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

    def create_internal_emitter(self, emitter=None):
        # connect to mycroft internal websocket
        self.emitter = emitter or WebsocketClient()
        self.register_internal_messages()
        self.emitter_thread = Thread(target=self.connect_to_internal_emitter)
        self.emitter_thread.setDaemon(True)
        self.emitter_thread.start()

    def register_internal_messages(self):
        self.emitter.on('speak', self.handle_speak)
        self.emitter.on('node_red.send', self.handle_send)

    # websocket handlers
    def register_client(self, client, platform=None):
        """
       Add client to list of managed connections.
       """
        platform = platform or "unknown"
        LOG.info("registering node_red: " + str(client.peer))
        t, ip, sock = client.peer.split(":")
        # see if ip adress is blacklisted
        if ip in self.ip_list and self.blacklist:
            LOG.warning("Blacklisted ip tried to connect: " + ip)
            self.unregister_client(client, reason=u"Blacklisted ip")
            return
        # see if ip adress is whitelisted
        elif ip not in self.ip_list and not self.blacklist:
            LOG.warning("Unknown ip tried to connect: " + ip)
            #  if not whitelisted kick
            self.unregister_client(client, reason=u"Unknown ip")
            return
        self.clients[client.peer] = {"object": client, "status":
            "connected", "platform": platform}
        context = {"source": client.peer}
        self.emitter.emit(
            Message("node_red.connect", {"peer": client.peer}, context))

    def unregister_client(self, client, code=3078,
                          reason=u"unregister client request"):
        """
       Remove client from list of managed connections.
       """
        LOG.info("deregistering node_red: " + str(client.peer))
        if client.peer in self.clients.keys():
            context = {"source": client.peer}
            self.emitter.emit(
                Message("node_red.disconnect",
                        {"reason": reason, "peer": client.peer},
                        context))
            client.sendClose(code, reason)
            self.clients.pop(client.peer)

    def process_message(self, client, payload, isBinary):
        """
       Process message from node, decide what to do internally here
       """
        LOG.info("processing message from client: " + str(client.peer))
        client_data = self.clients[client.peer]
        client_protocol, ip, sock_num = client.peer.split(":")
        # TODO update any client data you may want to store, ip, timestamp
        # etc.

        if isBinary:
            # TODO receive files ?
            pass
        else:
            message = Message.deserialize(payload)
            # add context for this message
            message.context["source"] = client.peer
            message.context["platform"] = "node_red"

            # This would be the place to check for blacklisted
            # messages/skills/intents per node instance

            # we could accept any kind of message for other purposes
            if message.type == "node_red.answer":
                # node is answering us
                message.type = "speak"
                message.context["destinatary"] = "node_fallback"
            elif message.type == "node_red.query":
                # node is asking us something
                message.context["client_name"] = "node_red"
                message.context["destinatary"] = client.peer
                message.type = "recognize_loop:utterance"
            elif message.type == "node_red.intent_failure":
                message.context["client_name"] = "node_red"
                message.context["destinatary"] = client.peer
            else:
                LOG.warning("node red sent an unexpected message type, "
                            "it was suppressed: " + message.type)
                return
            # send client message to internal mycroft bus
            self.emitter.emit(message)

    # mycroft handlers
    def handle_send(self, message):
        ''' mycroft wants to send a message to a node instance '''
        # send message to client
        msg = message.data.get("payload")
        is_file = message.data.get("isBinary", False)
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
            LOG.error("That client is not connected")
            self.emitter_send("node_red.send.error",
                              {"error": "Node Red is not connected",
                               "peer": peer},
                              message.context)

    def handle_speak(self, message):
        ''' capture speak answers for queries from node red '''
        # forward speak messages to node if that is the target
        client_name = message.context.get("client_name", "")
        if client_name == "node_red":
            peer = message.context.get("destinatary")
            if peer and peer in self.clients:
                client_data = self.clients[peer] or {}
                client = client_data.get("object")
                client.sendMessage(message.serialize(), False)
