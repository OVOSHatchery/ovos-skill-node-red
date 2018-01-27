Go away, seriously, it will just be frustrating if you try to use this code atm


# new internal mycroft-core messages

    "node_red.connect", {"peer": client.peer, "headers": request.headers}

    "node_red.connection.error", {"error": "invalid api key", "peer": client.peer, "api_key": api}

    "node_red.disconnect", {"peer": client.peer, "code": code, "reason": "connection closed", "wasClean": wasClean}

    "node_red.send", {"payload": {}, "peer": peer}

    "node_red.send.error", {"error": "Node Red is not connected", "peer": peer}