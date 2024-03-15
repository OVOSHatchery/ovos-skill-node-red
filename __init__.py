from ovos_bus_client.message import Message
from ovos_bus_client.message import dig_for_message
from ovos_workshop.skills.fallback import FallbackSkill
from ovos_workshop.decorators import intent_handler
from ovos_workshop.intents import IntentBuilder
from jarbas_hive_mind_red import get_listener
from jarbas_hive_mind.settings import CERTS_PATH
from jarbas_hive_mind.database import ClientDatabase
from ovos_utils import create_daemon
import time


class NodeRedSkill(FallbackSkill):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # can not reload, twisted reactor can not be restarted
        self.reload_skill = False
        if "timeout" not in self.settings:
            self.settings["timeout"] = 15
        if "secret" not in self.settings:
            self.settings["secret"] = "unsafe"
        if "priority" not in self.settings:
            self.settings["priority"] = 50

        # TODO pass these to hivemind / settingsmeta
        if "host" not in self.settings:
            self.settings["host"] = "127.0.0.1"
        if "port" not in self.settings:
            self.settings["port"] = 6789
        if "ip_list" not in self.settings:
            self.settings["ip_list"] = []
        if "ip_blacklist" not in self.settings:
            self.settings["ip_blacklist"] = True
        if "safe_mode" not in self.settings:
            self.settings["safe_mode"] = False
        if "message_whitelist" not in self.settings:
            self.settings["message_whitelist"] = []
        if "cert" not in self.settings:
            self.settings["cert"] = CERTS_PATH + '/red.crt'
        if "key" not in self.settings:
            self.settings["key"] = CERTS_PATH + '/red.key'
        if "ssl" not in self.settings:
            self.settings["ssl"] = False

        self.waiting_for_node = False
        self.conversing = False
        self.old_key = self.settings["secret"]
        self._error = None
        self.settings_change_callback = self.on_web_settings_change

    def initialize(self):

        self.register_fallback(self.handle_fallback,
                               int(self.settings["priority"]))

        self.add_event("node_red.success", self.handle_node_success)
        self.add_event("node_red.intent_failure", self.handle_node_failure)
        self.add_event("node_red.converse.activate",
                       self.handle_converse_enable)
        self.add_event("node_red.converse.deactivate",
                       self.handle_converse_disable)
        self.add_event("hive.client.connection.error", self.handle_wrong_key)
        self.converse_thread = create_daemon(self.converse_keepalive)
        self.node_setup()

    def on_web_settings_change(self):
        self.change_password()

    def change_password(self, force=False):

        with ClientDatabase() as db:
            mail = "nodered@fakemail.red"
            name = "nodered"
            key = self.settings["secret"]
            if not force:
                if self.old_key != key:
                    db.change_key(self.old_key, key)
                    self.old_key = key
                    self.speak_dialog("change_key", wait=True)
                    self.speak_dialog("please_reboot")
                    self.set_context("KEY_CHANGED")
            else:
                db.add_client(name, mail, key, crypto_key=None)

    @intent_handler(
        IntentBuilder("WhyRebootIntent").require("WhyKeyword").require(
            "KEY_CHANGED"))
    def handle_why_reboot(self, message):
        self.speak_dialog("why", wait=True)

    def handle_wrong_key(self, message):

        error = message.data.get("error")
        if self._error is None or error != self._error:
            self.speak_dialog("bad_key")
            self.speak(error)
        self._error = error

    def node_setup(self):
        self.change_password(force=True)
        self.node = get_listener(bus=self.bus)
        config = {
            "port": self.settings["port"],
            "host": self.settings["host"],
            "ssl": {
                "use_ssl": self.settings["ssl"]
            }
        }
        self.node.load_config(config)
        self.node._autorun = False
        self.node.listen()

    def shutdown(self):
        self.node.stop_from_thread()
        if self.converse_thread.running:
            self.converse_thread.join(2)
        super(NodeRedSkill, self).shutdown()

    def get_intro_message(self):
        # welcome dialog on skill install
        self.speak_dialog("intro")

    # node red control intents
    @intent_handler("pingnode.intent")
    def handle_ping_node(self, message):
        self.speak("ping")

        def pong(message):
            self.speak("pong")

        self.bus.once("node_red.pong", pong)

        message = message.forward("node_red.ping")
        self.bus.emit(message)

    @intent_handler("converse.enable.intent")
    def handle_converse_enable(self, message):
        if self.conversing:
            self.speak_dialog("converse_on")
        else:
            self.speak_dialog("converse_enable")
            self.conversing = True

    @intent_handler("converse.disable.intent")
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
        while True:
            if self.conversing:
                # avoid converse timed_out
                self.make_active()
            time.sleep(60)

    def converse(self, utterances, lang="en-us"):
        if self.conversing:
            message = dig_for_message()
            if message:
                message = message.reply("node_red.converse",
                                        {"utterance": utterances[0]})
            else:
                message = Message("node_red.converse",
                                  {"utterance": utterances[0]})

            if not message.context.get("platform",
                                       "").startswith("NodeRedMind"):
                self.bus.emit(message)
                return self.wait_for_node()
        return False

    # fallback
    def handle_fallback(self, message):
        message = message.reply("node_red.fallback", message.data)
        self.bus.emit(message)
        return self.wait_for_node()
