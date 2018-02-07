# node red fallback skill


[Node Red](https://nodered.org/) - Mycroft interface, on intent failure this skill will trigger node red


It also allows node red to ask mycroft


This [works by](https://github.com/JarbasAl/fallback-node-red/issues/2) opening a websocket and doing some messagebus magic


beginners and non technical users can now leverage visual programming and easily extend mycroft functionality



# Sample flow


flows should open a websocket connection to communicate with mycroft

    ws//username:secret@127.0.0.1:6789

![picture](https://github.com/JarbasAl/fallback-node-red/blob/master/flows.jpg)


# Importing the sample flow...

    Go to https://github.com/JarbasAl/fallback-node-red/blob/master/sample_flow.txt
    Copy the JSON text
    Go to http://addressofmycroft:1880
    In the upper righthand corner menu, choose... Import > Clipboard
    This will open the "Import nodes window"
    Paste the contents from the sample_flow.txt
    Click on Import and the flow should appear
    Next click on Deploy
    After you deploy, the websocket nodes should say 'connected' if the skill was installed properly


# Installing node red

on raspbian

    bash <(curl -sL https://raw.githubusercontent.com/node-red/raspbian-deb-package/master/resources/update-nodejs-and-nodered)

on debian/ubuntu

    curl -sL https://deb.nodesource.com/setup_8.x | sudo -E bash - sudo apt-get install -y nodejs
    sudo apt-get install npm
    sudo npm install -g --unsafe-perm node-red


# Node red auto start

node red must be running, it can be started with

     node-red-start

or made into a service

    sudo systemctl enable nodered.service
    sudo service nodered start
    check to see if node-red is running at http://127.0.0.1:1880

# Usage

    Input: ping node red
    Mycroft: node red says hello

    Input: echo
    Mycroft: this is echo

    Input: what does verge say
    Mycroft: Leading headline from the Verge: XXX

    Input: make node a priority skill
    Mycroft: node red is now triggered before mycroft

    Input: make node a priority skill
    Mycroft: node red is already a priority skill

    Input: make node a fallback skill
    Mycroft: node red restored to fallback skill

    Input: make node a fallback skill
    Mycroft: node red is already a fallback skill


# new internal mycroft-core messages

    "node_red.connect", {"peer": peer, "headers": request.headers}

    "node_red.connection.error", {"error": "invalid api key", "peer": peer, "api_key": api}

    "node_red.open", {"peer": peer}

    "node_red.disconnect", {"peer": peer, "code": code, "reason": "connection closed", "wasClean": wasClean}

    "node_red.send", {"payload": {}, "peer": peer}

    "node_red.broadcast", {"payload": {}}

    "node_red.send.error", {"error": "Node Red is not connected", "peer": peer, "payload": {}}

    "node_red.send.success", "data": {"peer": peer, "payload": {} }

    "node_red.intent_failure" -> ends waiting for fallback / returns False in converse

    "node_red.converse.activate" -> makes node red converse method always trigger first, keeps skill active until deactivated

    "node_red.converse.deactivate" -> stops node red converse method from triggering first, resumes fallback skill mode


# expected external messages from mycroft to node red

    "node_red.ask", {"utterance": ""} -> fallback/skill question

    "node_red.converse", {"utterance": ""} -> converse stage utterance

    "speak", {"utterance": ""}


# expected external messages from node.red to mycroft

    "node_red.answer", {"utterance": ""} -> becomes "speak", {"utterance": ""}, {"destinatary": "node_fallback"}

    "node_red.intent_failure", {"utterance": ""} -> ends waiting for fallback / returns false in converse

    "node_red.query", {"utterance": ""} -> becomes "recognizer_loop:utterance", {"utterances": [""]}, {"client_name": "node_red"}

    "node_red.converse.activate" -> makes node red converse method always trigger first, keeps skill active until deactivated

    "node_red.converse.deactivate" -> stops node red converse method from triggering first, resumes fallback skill mode



# security


allows using ssl in the websocket, automatically creates self signed certificates if none are provided, however node red will not [accept self signed](https://stackoverflow.com/a/30438204) out of the box


supports a safe-mode setting, unexpected message types from node red will be blocked


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
        if "priority" not in self.settings:
            self.settings["priority"] = 50


# fallback logs

    14:52:09.712 - SKILLS - DEBUG - {"type": "recognizer_loop:utterance", "data": {"utterances": ["echo"]}, "context": null}
    14:52:09.717 - SKILLS - DEBUG - {"type": "intent_failure", "data": {"lang": "en-us", "utterance": "echo"}, "context": {}}
    14:52:09.718 - mycroft.skills.padatious_service:handle_fallback:101 - DEBUG - Padatious fallback attempt: echo
    14:52:09.722 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.start", "data": {"handler": "fallback"}, "context": null}
    14:52:09.761 - SKILLS - DEBUG - {"type": "node_red.send", "data": {"peer": "tcp4:127.0.0.1:35390", "payload": {"type": "node_red.ask", "data": {"lang": "en-us", "utterance": "echo"}, "context": {}}}, "context": {}}
    14:52:09.762 - fallback-node-red__init__:handle_send:119 - INFO - sending
    14:52:09.780 - fallback-node-red__init__:onMessage:386 - INFO - Text message received: {"type": "node_red.answer", "data":{"utterance": "this is the echo"}, "context":{}}
    14:52:09.789 - SKILLS - DEBUG - {"type": "node_red.send.success", "data": {"peer": "tcp4:127.0.0.1:35390", "payload": {"data": {"lang": "en-us", "utterance": "echo"}, "type": "node_red.ask", "context": {}}}, "context": {}}
    14:52:09.790 - fallback-node-red__init__:process_message:513 - INFO - processing message from client: tcp4:127.0.0.1:35394
    14:52:09.796 - SKILLS - DEBUG - {"type": "speak", "data": {"utterance": "this is the echo"}, "context": {"source": "tcp4:127.0.0.1:35394", "ident": "test:tcp4:127.0.0.1:35394", "platform": "node_red", "destinatary": "node_fallback"}}
    14:52:10.022 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.complete", "data": {"handler": "fallback", "fallback_handler": "NodeRedSkill.handle_fallback"}, "context": null}

# node question logs

    14:45:42.967 - fallback-node-red__init__:onMessage:386 - INFO - Text message received: {"type": "node_red.query", "data":{"utterances" : ["node-red says hello world"]}, "context":{}}
    14:45:42.970 - fallback-node-red__init__:process_message:513 - INFO - processing message from client: tcp4:127.0.0.1:33718
    14:45:42.977 - SKILLS - DEBUG - {"type": "recognizer_loop:utterance", "data": {"utterances": ["node-red says hello world"]}, "context": {"source": "tcp4:127.0.0.1:33718", "client_name": "node_red", "ident": "test:tcp4:127.0.0.1:33718", "platform": "node_red", "destinatary": "tcp4:127.0.0.1:33718"}}
    14:45:43.087 - SKILLS - DEBUG - {"type": "-4273373871611945018:HelloWorldIntent", "data": {"confidence": 1.0, "target": null, "intent_type": "-4273373871611945018:HelloWorldIntent", "HelloWorldKeyword": "hello world", "__tags__": [{"end_token": 3, "start_token": 2, "from_context": false, "entities": [{"confidence": 1.0, "data": [["hello world", "HelloWorldKeyword"]], "key": "hello world", "match": "hello world"}], "key": "hello world", "match": "hello world"}], "utterance": "node-red says hello world"}, "context": {"ident": "test:tcp4:127.0.0.1:33718", "target": null, "platform": "node_red", "client_name": "node_red", "destinatary": "tcp4:127.0.0.1:33718", "source": "tcp4:127.0.0.1:33718"}}
    14:45:43.093 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.start", "data": {"handler": "HelloWorldSkill.handle_hello_world_intent"}, "context": null}
    14:45:43.126 - SKILLS - DEBUG - {"type": "speak", "data": {"expect_response": false, "utterance": "Hello world"}, "context": {"ident": "test:tcp4:127.0.0.1:33718", "target": null, "platform": "node_red", "client_name": "node_red", "destinatary": "tcp4:127.0.0.1:33718", "source": "tcp4:127.0.0.1:33718"}}
    14:45:43.133 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.complete", "data": {"handler": "HelloWorldSkill.handle_hello_world_intent"}, "context": null}
    14:45:43.173 - SKILLS - DEBUG - {"type": "node_red.send.success", "data": {"peer": "broadcast", "payload": {"data": {"expect_response": false, "utterance": "Hello world"}, "type": "speak", "context": {"ident": "test:tcp4:127.0.0.1:33718", "target": null, "platform": "node_red", "client_name": "node_red", "destinatary": "tcp4:127.0.0.1:33718", "source": "tcp4:127.0.0.1:33718"}}}, "context": {"ident": "test:tcp4:127.0.0.1:33718", "target": null, "platform": "node_red", "client_name": "node_red", "destinatary": "tcp4:127.0.0.1:33718", "source": "tcp4:127.0.0.1:33718"}}


# asking node red from an intent logs

    14:43:18.865 - SKILLS - DEBUG - {"type": "-7976428735325913512:pingnode.intent", "data": {"utterance": "ping node red"}, "context": null}
    14:43:18.866 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.complete", "data": {"handler": "fallback", "fallback_handler": "PadatiousService.handle_fallback"}, "context": null}
    14:43:18.869 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.start", "data": {"handler": "NodeRedSkill.handle_ping_node"}, "context": null}
    14:43:18.893 - SKILLS - DEBUG - {"type": "node_red.send", "data": {"payload": {"type": "node_red.ask", "data": {"utterance": "hello"}, "context": null}}, "context": {}}
    14:43:18.894 - fallback-node-red__init__:handle_send:119 - INFO - sending
    14:43:18.901 - fallback-node-red__init__:onMessage:386 - INFO - Text message received: {"type": "node_red.answer", "data":{"utterance": "node-red says hey"}, "context":{}}
    14:43:18.904 - fallback-node-red__init__:process_message:513 - INFO - processing message from client: tcp4:127.0.0.1:33718
    14:43:18.905 - SKILLS - DEBUG - {"type": "mycroft.skill.handler.complete", "data": {"handler": "NodeRedSkill.handle_ping_node"}, "context": null}
    14:43:18.905 - SKILLS - DEBUG - {"type": "node_red.send.broadcast", "data": {"peer": null, "payload": {"data": {"utterance": "hello"}, "type": "node_red.ask", "context": null}}, "context": {}}
    14:43:18.945 - SKILLS - DEBUG - {"type": "speak", "data": {"utterance": "node-red says hey"}, "context": {"source": "tcp4:127.0.0.1:33718", "ident": "test:tcp4:127.0.0.1:33718", "platform": "node_red", "destinatary": "node_fallback"}}


# extra

if converse method is activated node red will work as a priority skill, all
utterances will go to node red until converse mode is explicitly disabled, it
does not time out

without being explicitly activated converse method is fully ignored

converse method returns False in case of timeout or intent_failure

fallback is ignored if converse is active, they are mutually exclusive, this
can be handled from inside node red if needed

other skills can use the new bus messages to send data to node red, the node
red entry point can be targeted if desired by specifying the peer in the
message data, if no peer is specified message is broadcast


1 peer = 1 websocket connection inside a node red flow


peer can be a websocket name ( fallback ) or socket ( tcp4:127.0.0.1:33718 )


    def handle_ping_node(self, message):
        self.emitter.emit(message.reply("node_red.send",
                                        {"payload": {"type": "node_red.ask",
                                                     "data": {
                                                         "utterance": "hello"},
                                                     "context": message
                                                     .context},
                                         "peer": None}))


each socket connection can provide a name on connection

    ws//name_for_this_socket_connection:secret@127.0.0.1:6789


fallback skill always searches for a connection named "fallback", on fail broadcasts


answers to node red searches for a connection named "answer", on fail broadcasts


node red can be running in other machine as long as it can access mycroft ip address to initiate the connection


# TODOS and known bugs

- TODO settingsmeta.json
- TODO launch node red on start up, currently needs to be started by user
- BUG self signed ssl fails
- TODO get a PEM-encoding of the self-signed certificate and include it as a CA. Since the certificate is self-signed, it acts as its own CA and therefore can be used to verify itself.
- TODO make ssl a default
- BUG msm node red install fails in non-raspberry pi
- TODO node red install for non debian based OS


# liked this?

- https://www.patreon.com/jarbasAI
- https://www.paypal.me/jarbasAI