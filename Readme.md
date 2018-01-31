# node red fallback skill


Node Red - Mycroft interface, on intent failure this skill will trigger node
red


It also allows node red to ask mycroft


This works by opening a websocket and doing some messagebus magic


beginners and non technical users can now leverage visual programming and
easily extend mycroft functionality


# Sample flow


flows should open a websocket connection to communicate with mycroft

    ws//username:secret@127.0.0.1:6789

TODO pic


# Usage

TODO


# new internal mycroft-core messages

    "node_red.connect", {"peer": peer, "headers": request.headers}

    "node_red.connection.error", {"error": "invalid api key", "peer": peer, "api_key": api}

    "node_red.open", {"peer": peer}

    "node_red.disconnect", {"peer": peer, "code": code, "reason": "connection closed", "wasClean": wasClean}

    "node_red.send", {"payload": {}, "peer": peer}

    "node_red.broadcast", {"payload": {}}

    "node_red.send.error", {"error": "Node Red is not connected", "peer": peer, "payload": {}}

    "node_red.send.success", "data": {"peer": peer, "payload": {} }

    "node_red.intent_failure" -> ends waiting for fallback



# expected external messages from mycroft to node red

    "node_red.ask", {"utterance": ""}

    "speak", {"utterance": ""}


# expected external messages from node.red to mycroft

    "node_red.answer", {"utterance": ""} -> becomes "speak", {"utterance": ""}, {"destinatary": "node_fallback"}

    "node_red.intent_failure", {"utterance": ""} -> ends waiting for fallback

    "node_red.query", {"utterance": ""} -> becomes "recognizer_loop:utterance", {"utterances": [""]}, {"client_name": "node_red"}



# security


allows using ssl in the websocket, create self signed certificates if none are
 provided, however node red will not [accept self signed](https://stackoverflow.com/a/30438204) out of the box


 supports a safe-mode setting, unexpected message types from node red will be
 blocked


 requires a secret key in the headers to connect to websocket


 supports ip blacklist / whitelist



# Settings

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
        if "message_whitelist" not in self.settings:
            self.settings["message_whitelist"] = []
        if "safe_mode" not in self.settings:
            self.settings["safe_mode"] = False


# fallback logs

TODO

# node question logs

TODO

# extra

other skill can use the new bus messages to send data to node red, the node
red entry point can be targeted if desired by specifying the peer

# TODOS and known bugs

- launch node red on start up, currently needs to be started by user
- self signed ssl fails
- make ssl a default
- node red install fails in non-raspberry pi
- node red install for non debian based OS