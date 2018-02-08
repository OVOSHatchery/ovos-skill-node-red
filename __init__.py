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
import os
import time
import base64
import json
import unicodedata
from twisted.internet import reactor, ssl
from twisted.internet.error import ReactorNotRunning
from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory
from autobahn.websocket.types import ConnectionDeny

from mycroft.messagebus.message import Message
from mycroft.skills.core import FallbackSkill
try:
    from mycroft.skills.core import dig_for_message
except ImportError:
    # < 0.9.14 mycroft versions

    import inspect


    def dig_for_message():
        """
            Dig Through the stack for message.
        """
        stack = inspect.stack()
        # Limit search to 10 frames back
        stack = stack if len(stack) < 10 else stack[:10]
        local_vars = [frame[0].f_locals for frame in stack]
        for l in local_vars:
            if 'message' in l and isinstance(l['message'], Message):
                return l['message']

from mycroft.util.log import LOG

__author__ = "jarbas"


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
            self.settings["timeout"] = 15
        if "ssl" not in self.settings:
            self.settings["ssl"] = False
        if "secret" not in self.settings:
            self.settings["secret"] = "test_key"
        if "ip_list" not in self.settings:
            self.settings["ip_list"] = []
        if "ip_blacklist" not in self.settings:
            self.settings["ip_blacklist"] = True
        if "safe_mode" not in self.settings:
            self.settings["safe_mode"] = False
        if "message_whitelist" not in self.settings:
            self.settings["message_whitelist"] = []
        if "priority" not in self.settings:
            self.settings["priority"] = 50
        self.waiting_for_node = False
        self.waiting_for_mycroft = False
        self.factory = None
        self.conversing = False
        self.converse_thread = Thread(target=self.converse_keepalive)
        self.converse_thread.setDaemon(True)

    def get_intro_message(self):
        # we could return the string or do this
        self.speak_dialog("intro")

    def initialize(self):
        prot = "wss" if self.settings["ssl"] else "ws"
        self.address = unicode(prot) + u"://" + \
                       unicode(self.settings["host"]) + u":" + \
                       unicode(self.settings["port"]) + u"/"
        self.factory = NodeRedFactory(self.address)
        self.factory.protocol = NodeRedProtocol
        self.factory.settings = self.settings
        self.factory.bind(self.emitter)
        self.node_process = Thread(target=self.connect_to_node)
        self.node_process.setDaemon(True)
        self.node_process.start()

        LOG.info("Listening for node red connections on " + self.address)

        # self.emitter.on("speak", self.handle_node_answer)
        self.emitter.on("node_red.intent_failure", self.handle_node_failure)
        self.emitter.on("node_red.send", self.handle_send)
        self.emitter.on("node_red.converse.activate", self.handle_converse_on)
        self.emitter.on("node_red.converse.deactivate",
                        self.handle_converse_off)
        # node ask mycroft
        self.emitter.on("recognizer_loop:utterance", self.handle_node_query)
        self.emitter.on("complete_intent_failure", self.handle_node_question)
        self.emitter.on("speak", self.handle_node_question)

        self.register_fallback(self.handle_fallback, self.settings["priority"])
        self.register_intent_file("pingnode.intent", self.handle_ping_node)
        self.register_intent_file("converse.enable.intent",
                                  self.handle_converse_enable)
        self.register_intent_file("converse.disable.intent",
                                  self.handle_converse_disable)

    def connect_to_node(self):
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
            contextFactory = ssl.DefaultOpenSSLContextFactory(
                self.settings["key"],
                self.settings["cert"])

            reactor.listenSSL(self.settings["port"],
                              self.factory,
                              contextFactory)
        else:
            reactor.listenTCP(self.settings["port"], self.factory)
        reactor.run(installSignalHandlers=0)

    # mycroft handlers
    def handle_send(self, message):
        ''' mycroft wants to send a message to a node instance '''
        # send message to client
        LOG.info("sending")
        msg = message.data.get("payload")
        is_file = message.data.get("isBinary", False)
        peer = message.data.get("peer")
        ident = message.context.get("ident")
        if not peer and ident:
            name = ident.split(":")[0]
            peer = ":".join(ident.split(":")[1:])
        elif peer and ":" not in peer:
            # name provided
            peer = self.factory.get_peer_by_name(peer)
            if not len(peer):
                peer = None
            else:
                peer = peer[0]
        if self.factory is None:
            LOG.error("factory not ready")
            return
        try:
            if is_file:
                # TODO send file
                self.emitter.emit(message.reply("node_red.send.error",
                                                {
                                                    "error": "binary files not supported",
                                                    "peer": peer,
                                                    "payload": msg}))
            elif peer is None:
                # send message to client
                self.factory.broadcast_message(msg)
                self.emitter.emit(message.reply("node_red.send.broadcast",
                                                {"peer": peer,
                                                 "payload": msg}))
            else:
                # send message to client
                if self.factory.send_message(peer, msg):
                    self.emitter.emit(message.reply("node_red.send.success",
                                                    {"peer": peer,
                                                     "payload": msg}))
                else:
                    LOG.error("That client is not connected")
                    self.emitter.emit(message.reply("node_red.send.error",
                                                    {"error": "unknown error",
                                                     "peer": peer,
                                                     "payload": msg}))
        except Exception as e:
            LOG.error(e)

    def handle_node_query(self, message):
        message.context = message.context or {}
        client_name = message.context.get("client_name", "")
        if client_name == "node_red":
            self.waiting_for_mycroft = message.context.get("destinatary")

    def handle_node_question(self, message):
        ''' capture speak answers for queries from node red '''
        message.context = message.context or {}
        destinatary = message.context.get("destinatary", "")
        client_name = message.context.get("client_name", "")
        # capture answers from node
        if not self.waiting_for_mycroft and not self.waiting_for_node:
            return

        if destinatary == "node_fallback" and self.waiting_for_node:
            self.waiting_for_node = False
            self.success = True
            return

        # forward speak messages to node if that is the target
        if message.type == "complete_intent_failure" and self.waiting_for_mycroft:
            self.waiting_for_mycroft = False

        peers = self.factory.get_peer_by_name("answer")
        if not len(peers):
            self.factory.broadcast_message(message)
            self.emitter.emit(message.reply("node_red.send.success",
                                            {"peer": "broadcast",
                                             "payload": {
                                                 "type": message.type,
                                                 "data": message.data,
                                                 "context": message.context}}))
        else:
            for peer in peers:
                self.factory.send_message(peer, message)
                self.emitter.emit(message.reply("node_red.send.success",
                                                {"peer": peer,
                                                 "payload": {
                                                     "type": message.type,
                                                     "data": message.data,
                                                     "context": message.context}}))

    def handle_node_failure(self, message):
        ''' node answered us, signal end of fallback '''
        self.waiting_for_node = False
        self.success = False

    def wait_for_node(self):
        start = time.time()
        self.waiting_for_node = True
        while self.waiting_for_node and time.time() - start < self.settings[
            "timeout"]:
            time.sleep(0.3)

    def handle_fallback(self, message):
        # dont answer self
        message.context = message.context or {}
        platform = message.context.get("platform", "mycroft")
        if platform == "node_red" or self.conversing:
            return False
        # ask node
        self.success = False
        peers = self.factory.get_peer_by_name("fallback")
        if len(peers):
            for peer in peers:
                self.emitter.emit(message.reply("node_red.send",
                                                {"payload": {
                                                    "type": "node_red.ask",
                                                    "data": message.data,
                                                    "context":
                                                        message.context},
                                                 "peer": peer}))

                self.wait_for_node()
                if self.waiting_for_node:
                    self.emitter.emit(
                        message.reply("node_red.timeout", message.data))
                    self.waiting_for_node = False
                elif self.success:
                    break
        else:
            self.emitter.emit(message.reply("node_red.send",
                                            {"payload": {
                                                "type": "node_red.ask",
                                                "data": message.data,
                                                "context":
                                                    message.context}}))
            self.wait_for_node()
            if self.waiting_for_node:
                self.emitter.emit(
                    message.reply("node_red.timeout", message.data))
                self.waiting_for_node = False
        return self.success

    def handle_ping_node(self, message):
        self.emitter.emit(message.reply("node_red.send",
                                        {"payload": {"type": "node_red.ask",
                                                     "data": {
                                                         "utterance": "hello"},
                                                     "context": message.context}}))

    def stop_reactor(self):
        """Stop the reactor and join the reactor thread until it stops.
        """

        def stop_reactor():
            '''Helper for calling stop from withing the thread.'''
            try:
                reactor.stop()
            except ReactorNotRunning:
                LOG.info("twisted reactor stopped")
            except Exception as e:
                LOG.error(e)

        self.factory.shutdown()
        self.factory = None

        reactor.callFromThread(stop_reactor)
        for p in reactor.getDelayedCalls():
            if p.active():
                p.cancel()

    def shutdown(self):
        self.converse_thread.join(2)
        self.node_process.join(2)
        self.stop_reactor()
        self.emitter.remove("node_red.intent_failure",
                            self.handle_node_failure)
        self.emitter.remove("node_red.send", self.handle_send)
        self.emitter.remove("speak", self.handle_node_question)
        self.emitter.remove("recognizer_loop:utterance",
                            self.handle_node_query)
        self.emitter.remove("complete_intent_failure",
                            self.handle_node_question)
        self.emitter.remove("node_red.converse.activate",
                            self.handle_converse_on)
        self.emitter.remove("node_red.converse.deactivate",
                            self.handle_converse_off)
        super(NodeRedSkill, self).shutdown()

    def converse_keepalive(self):
        start = time.time()
        while self.conversing:
            if time.time() - start >= 5 * 60:
                # converse timed_out
                self.make_active()
                start = time.time()
            time.sleep(1)

    def handle_converse_enable(self, message):
        if self.conversing:
            self.speak_dialog("converse_on")
        else:
            self.speak_dialog("converse_enable")
            self.handle_converse_on(message)

    def handle_converse_disable(self, message):
        if not self.conversing:
            self.speak_dialog("converse_off")
        else:
            self.speak_dialog("converse_disable")
            self.handle_converse_off(message)

    def handle_converse_on(self, message):
        self.conversing = True
        self.make_active()
        self.converse_thread.start()

    def handle_converse_off(self, message):
        self.conversing = False
        self.converse_thread.join()

    def converse(self, utterances, lang="en-us"):
        if self.conversing:
            message = dig_for_message()
            data = {"payload": {
                                "type": "node_red.converse",
                                "data": {"utterance": utterances[0]},
                                "context": {"source": self.name}
                                }
                    }
            if message:
                message = message.reply("node_red.send", data)
            else:
                message = Message("node_red.send", data)

            self.factory.broadcast_message(message)
            self.success = False
            self.wait_for_node()
            if self.waiting_for_node:
                self.emitter.emit(
                    Message("node_red.timeout", {"source": self.name}))
                self.waiting_for_node = False
                return False
            return self.success
        return False


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
        if usernamePasswordEncoded is None:
            api = ""
        else:
            usernamePasswordEncoded = usernamePasswordEncoded.split()
            usernamePasswordDecoded = base64.b64decode(
                usernamePasswordEncoded[1])
            self.name, api = usernamePasswordDecoded.split(":")
        context = {"source": self.peer}
        self.platform = "node_red"
        # send message to internal mycroft bus
        data = {"peer": request.peer, "headers": request.headers}
        self.factory.emitter_send("node_red.connect", data, context)

        if api != self.factory.settings["secret"]:
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
        # send message to internal mycroft bus
        data = {"peer": self.peer}
        context = {"source": self.peer}
        self.factory.emitter_send("node_red.open", data, context)

    def onMessage(self, payload, isBinary=False):
        if isBinary:
            LOG.info(
                "Binary message received: {0} bytes".format(len(payload)))
        else:
            LOG.info(
                "Text message received: {0}".format(unicodedata.normalize(
                    'NFKD', unicode(payload)).encode('ascii', 'ignore')))

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
    clients = {}

    @classmethod
    def get_peer_by_name(cls, name):
        names = []
        for peer in cls.clients:
            peer_name = cls.clients[peer]["name"]
            if name == peer_name:
                names.append(peer)
        return names

    @classmethod
    def send_message(cls, peer, data):
        if isinstance(data, Message):
            data = Message.serialize(data)
        payload = repr(json.dumps(data))
        if peer in cls.clients:
            c = cls.clients[peer]["object"]
            reactor.callFromThread(c.sendMessage, payload)
            return True
        return False

    @classmethod
    def broadcast_message(cls, data):
        if isinstance(data, Message):
            payload = Message.serialize(data)
        else:
            payload = repr(json.dumps(data))
        for c in set(cls.clients):
            c = cls.clients[c]["object"]
            reactor.callFromThread(c.sendMessage, payload)

    def __init__(self, *args, **kwargs):
        super(NodeRedFactory, self).__init__(*args, **kwargs)
        # list of connected clients
        self.settings = {"ip_blacklist": True, "ip_list": [], "secret":
            "test_key"}
        # mycroft_ws
        self.emitter = None

    @classmethod
    def shutdown(cls):
        while len(cls.clients):
            try:
                peer = cls.clients.keys()[0]
                client = cls.clients[peer]["object"]
                client.sendClose()
                cls.clients.pop(peer)
            except Exception as e:
                LOG.warning(e)

    def bind(self, emitter):
        self.emitter = emitter

    def emitter_send(self, type, data=None, context=None):
        data = data or {}
        context = context or {}
        self.emitter.emit(Message(type, data, context))

    # websocket handlers
    def register_client(self, client, platform=None):
        """
       Add client to list of managed connections.
       """
        platform = platform or "unknown"
        LOG.info("registering node_red: " + str(client.peer))
        t, ip, sock = client.peer.split(":")
        # see if ip adress is blacklisted
        if ip in self.settings["ip_list"] and self.settings["ip_blacklist"]:
            LOG.warning("Blacklisted ip tried to connect: " + ip)
            self.unregister_client(client, reason=u"Blacklisted ip")
            return
        # see if ip adress is whitelisted
        elif ip not in self.settings["ip_list"] and not self.settings[
            "ip_blacklist"]:
            LOG.warning("Unknown ip tried to connect: " + ip)
            #  if not whitelisted kick
            self.unregister_client(client, reason=u"Unknown ip")
            return
        self.clients[client.peer] = {"object": client, "status":
            "connected", "platform": platform, "name": client.name}

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
            message.context["ident"] = client.name + ":" + client.peer

            # This would be the place to check for blacklisted
            # messages/skills/intents per node instance

            # we can accept any kind of message for other purposes
            message.context["client_name"] = "node_red"
            message.context["destinatary"] = client.peer
            if message.type == "node_red.answer":
                # node is answering us, do not use target, we want tts to
                # execute
                message.type = "speak"
                message.context["destinatary"] = "node_fallback"
            elif message.type == "node_red.query":
                # node is asking us something
                message.type = "recognizer_loop:utterance"
                # we do not want tts to execute, unless explicitly requested
                if "target" not in message.context:
                    message.context["target"] = "node_red"
            elif message.type == "node_red.intent_failure":
                # node red failed
                LOG.info("node red intent failure")
            elif message.type == "node_red.converse.deactivate":
                LOG.info("node red converse deactivate")
            elif message.type == "node_red.converse.activate":
                LOG.info("node red converse activate")
            elif self.settings["safe_mode"] and message.type not in \
                    self.settings["message_whitelist"]:
                LOG.warning("node red sent an unexpected message type, "
                            "it was suppressed: " + message.type)
                return
            # send client message to internal mycroft bus
            self.emitter.emit(message)

