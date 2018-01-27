Go away, seriously, it will just be frustrating if you try to use this code atm


# new internal mycroft-core messages

    "node_red.connect", {"peer": client.peer, "headers": request.headers}

    "node_red.connection.error", {"error": "invalid api key", "peer": client.peer, "api_key": api}

    "node_red.disconnect", {"peer": client.peer, "code": code, "reason": "connection closed", "wasClean": wasClean}

    "node_red.send", {"payload": {}, "peer": peer}

    "node_red.send.error", {"error": "Node Red is not connected", "peer": peer}


# expected external messages from mycroft to node red

    "node_red.ask", {"utterance": ""}

    "speak", {"utterance": ""}

# expected external messages from node.red to mycroft

    "node_red.answer", {"utterance": ""} -> becomes "speak", {"utterance": ""}, {"destinatary": "node_fallback"}

    "node_red.query", {"utterance": ""} -> becomes "recognizer_loop:utterance", {"utterances": [""]}, {"client_name": "node_red"}