from mycroft.messagebus.message import Message, dig_for_message
from mycroft.skills.core import FallbackSkill, intent_file_handler

from jarbas_hive_mind_red import get_listener
from jarbas_hive_mind.settings import CERTS_PATH
from jarbas_hive_mind.database import ClientDatabase
from jarbas_utils import create_daemon
import time


class NodeRedSkill(FallbackSkill):
    def __init__(self):
        super(NodeRedSkill, self).__init__(name='NodeRedSkill')
        # can not reload, twisted reactor can not be restarted
        self.reload_skill = False
        if "host" not in self.settings:
            self.settings["host"] = "127.0.0.1"
        if "port" not in self.settings:
            self.settings["port"] = 6789
        if "cert" not in self.settings:
            self.settings["cert"] = CERTS_PATH + '/red.crt'
        if "key" not in self.settings:
            self.settings["key"] = CERTS_PATH + '/red.key'
        if "timeout" not in self.settings:
            self.settings["timeout"] = 15
        if "ssl" not in self.settings:
            self.settings["ssl"] = False
        if "secret" not in self.settings:
            self.settings["secret"] = "unsafe"
        if "priority" not in self.settings:
            self.settings["priority"] = 50
            
        # TODO pass these to hivemind
        if "ip_list" not in self.settings:
            self.settings["ip_list"] = []
        if "ip_blacklist" not in self.settings:
            self.settings["ip_blacklist"] = True
        if "safe_mode" not in self.settings:
            self.settings["safe_mode"] = False
        if "message_whitelist" not in self.settings:
            self.settings["message_whitelist"] = []
            
        self.waiting_for_node = False
        self.conversing = False

    def initialize(self):
        self.register_fallback(self.handle_fallback,
                               int(self.settings["priority"]))

        self.add_event("node_red.success", self.handle_node_success)
        self.add_event("node_red.intent_failure", self.handle_node_failure)
        self.add_event("node_red.converse.activate",
                       self.handle_converse_enable)
        self.add_event("node_red.converse.deactivate",
                       self.handle_converse_disable)
        self.converse_thread = create_daemon(self.converse_keepalive)
        self.node_setup()

    def node_setup(self):
        config = {
            "port": self.settings["port"],
            "host": self.settings["host"],
            "ssl":
                {"use_ssl": self.settings["ssl"]}

        }

        with ClientDatabase() as db:
            mail = "nodered@fakemail.red"
            name = "nodered"
            key = self.settings["secret"]
            db.add_client(name, mail, key)

        self.node = get_listener(bus=self.bus)
        self.node.load_config(config)
        self.node_thread = create_daemon(self.node.listen)
        
    def shutdown(self):
        self.node.stop_from_thread()
        if self.converse_thread.running:
            self.converse_thread.join(2)
        super(NodeRedSkill, self).shutdown()

    def get_intro_message(self):
        # welcome dialog on skill install
        self.speak_dialog("intro")

    # node red control intents
    @intent_file_handler("pingnode.intent")
    def handle_ping_node(self, message):
        self.speak("ping")

        def pong(message):
            self.speak("pong")

        self.bus.once("node_red.pong", pong)

        message = message.forward("node_red.ping")
        self.bus.emit(message)

    @intent_file_handler("converse.enable.intent")
    def handle_converse_enable(self, message):
        if self.conversing:
            self.speak_dialog("converse_on")
        else:
            self.speak_dialog("converse_enable")
            self.conversing = True

    @intent_file_handler("converse.disable.intent")
    def handle_converse_disable(self, message):
        if not self.conversing:
            self.speak_dialog("converse_off")
        else:
            self.speak_dialog("converse_disable")
            self.conversing = False
    
    # node red event handlers
    def handle_node_success(self, message):
        self.waiting_for_node = False
        self.success = True

    def handle_node_failure(self, message):
        self.waiting_for_node = False
        self.success = False

    def wait_for_node(self):
        start = time.time()
        self.success = False
        self.waiting_for_node = True
        while self.waiting_for_node and \
                time.time() - start < float(self.settings["timeout"]):
            time.sleep(0.1)
        if self.waiting_for_node:
            message = dig_for_message()
            if not message:
                message = Message("node_red.timeout")
            else:
                message.reply("node_red.timeout")
            self.bus.emit(message)
            self.waiting_for_node = False
        return self.success

    # converse
    def converse_keepalive(self):
        start = time.time()
        while True:
            if self.conversing and time.time() - start >= 5 * 60:
                # converse timed_out
                self.make_active()
                start = time.time()
            time.sleep(1)

    def converse(self, utterances, lang="en-us"):
        if self.conversing:
            message = dig_for_message()
            if message:
                message = message.reply("node_red.converse",
                                        {"utterance": utterances[0]})
            else:
                message = Message("node_red.converse",
                                  {"utterance": utterances[0]})

            if not message.context.get("platform", "").startswith(
                    "NodeRedMind"):
                self.bus.emit(message)
                return self.wait_for_node()
        return False

    # fallback
    def handle_fallback(self, message):
        message = message.reply("node_red.fallback", message.data)
        self.bus.emit(message)
        return self.wait_for_node()


def create_skill():
    return NodeRedSkill()
