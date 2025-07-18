import socket
import threading
from vector_clock import VectorClock
from message import create_message, parse_message

class Node:
    def __init__(self, node_id, all_nodes, port, peers):
        self.node_id = node_id
        self.vc = VectorClock(node_id, all_nodes)
        self.data = {}
        self.port = port
        self.peers = peers  # list of (host, port)

    def start(self):
        threading.Thread(target=self.listen, daemon=True).start()
        print(f"[{self.node_id}] Démarré sur le port {self.port}")
        while True:
            cmd = input(">>> ")
            if cmd.startswith("set"):
                _, key, value = cmd.split()
                self.set_key(key, value)

    def listen(self):
        s = socket.socket()
        s.bind(('localhost', self.port))
        s.listen()
        while True:
            conn, _ = s.accept()
            data = conn.recv(4096)
            if data:
                msg = parse_message(data)
                self.handle_message(msg)

    def handle_message(self, msg):
        sender = msg["sender"]
        clock = msg["clock"]
        key = msg["key"]
        value = msg["value"]

        conflict = False
        if key in self.data:
            existing_clock = self.data[key]["clock"]
            if not self.vc.happens_before(clock) and not self.happens_after(clock, existing_clock):
                conflict = True

        if conflict:
            print(f"[{self.node_id}] ⚠️ Conflit détecté sur {key} avec {sender}")
            self.data[key] = {"value": value, "clock": clock}
        else:
            self.vc.update(clock)
            self.data[key] = {"value": value, "clock": clock}
            print(f"[{self.node_id}] ✅ Reçu {key} = {value} de {sender}")

    def happens_after(self, c1, c2):
        return all(c1[k] >= c2[k] for k in c1) and any(c1[k] > c2[k] for k in c1)

    def set_key(self, key, value):
        self.vc.increment()
        self.data[key] = {"value": value, "clock": self.vc.to_dict()}
        msg = create_message(self.node_id, self.vc.to_dict(), key, value)
        for host, port in self.peers:
            self.send_message(host, port, msg)

    def send_message(self, host, port, msg):
        try:
            s = socket.socket()
            s.connect((host, port))
            s.send(msg)
            s.close()
        except:
            print(f"[{self.node_id}] ❌ Échec d'envoi à {host}:{port}")
