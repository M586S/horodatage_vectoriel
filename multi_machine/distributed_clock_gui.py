import socket
import threading
import tkinter as tk
import json
import os
import time

# ==========================
# CONFIGURATION DU SYSTÈME
# ==========================

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"

# Exemple de config.json attendu :
# {
#   "name": "A",
#   "port": 5000,
#   "peers": {
#     "B": ["192.168.1.11", 5001],
#     "C": ["192.168.1.12", 5002]
#   },
#   "password": "simpleauth"
# }

with open(CONFIG_FILE, 'r') as f:
    CONFIG = json.load(f)

# ==========================
# CLASSE HORLOGE VECTORIELLE
# ==========================

class VectorClock:
    def __init__(self, name, peers):
        self.name = name
        self.clock = {name: 0}
        for peer in peers:
            self.clock[peer] = 0
        self.history = []

    def tick(self):
        self.clock[self.name] += 1
        self.log_event("Local event")

    def update(self, incoming_clock):
        for peer, time in incoming_clock.items():
            self.clock[peer] = max(self.clock.get(peer, 0), time)
        self.clock[self.name] += 1
        self.log_event("Received event")

    def log_event(self, event_type):
        snapshot = self.clock.copy()
        self.history.append((event_type, snapshot))

    def to_dict(self):
        return self.clock

    def load_state(self, state):
        self.clock = state.get("clock", self.clock)
        self.history = state.get("history", self.history)

    def save_state(self):
        return {"clock": self.clock, "history": self.history}

# ==========================
# COMMUNICATION RÉSEAU
# ==========================

class NetworkHandler:
    def __init__(self, clock, display_callback):
        self.clock = clock
        self.display_callback = display_callback
        self.running = True

        self.peers = CONFIG["peers"]
        self.port = CONFIG["port"]
        self.password = CONFIG["password"]

        self.server_thread = threading.Thread(target=self.run_server, daemon=True)
        self.server_thread.start()

    def run_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", self.port))
        s.listen()

        while self.running:
            try:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_connection, args=(conn,), daemon=True).start()
            except:
                continue

    def handle_connection(self, conn):
        try:
            data = conn.recv(4096).decode()
            msg = json.loads(data)
            if msg.get("password") != self.password:
                conn.close()
                return
            if "clock" in msg:
                self.clock.update(msg["clock"])
                self.display_callback()
        except Exception as e:
            print("Erreur réseau:", e)
        finally:
            conn.close()

    def send_to_peer(self, peer_name):
        if peer_name not in self.peers:
            return

        ip, port = self.peers[peer_name]
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((ip, port))
            msg = {
                "password": self.password,
                "clock": self.clock.to_dict()
            }
            s.send(json.dumps(msg).encode())
            s.close()
        except:
            self.display_callback(f"[!] Impossible de joindre {peer_name} — retrying dans 5s")
            # Relance automatique après 5 secondes
            threading.Timer(5, self.send_to_peer, args=(peer_name,)).start()

# ==========================
# SAUVEGARDE/CHARGEMENT
# ==========================

def save_local_state(clock):
    with open(STATE_FILE, "w") as f:
        json.dump(clock.save_state(), f)

def load_local_state(clock):
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            clock.load_state(state)

# ==========================
# INTERFACE GRAPHIQUE
# ==========================

class ClockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Node {CONFIG['name']} - Vector Clock")

        self.clock = VectorClock(CONFIG["name"], CONFIG["peers"].keys())
        load_local_state(self.clock)

        self.network = NetworkHandler(self.clock, self.update_display)

        self.label = tk.Label(root, text="", font=("Courier", 14), justify="left")
        self.label.pack(padx=10, pady=10)

        self.event_button = tk.Button(root, text="🔄 Événement local", command=self.local_event)
        self.event_button.pack(fill='x', padx=10, pady=5)

        for peer in CONFIG["peers"]:
            b = tk.Button(root, text=f"📡 Envoyer à {peer}", command=lambda p=peer: self.send_event(p))
            b.pack(fill='x', padx=10, pady=2)

        self.save_button = tk.Button(root, text="💾 Sauvegarder", command=self.save)
        self.save_button.pack(fill='x', padx=10, pady=5)

        self.history_button = tk.Button(root, text="🕓 Afficher historique", command=self.show_history)
        self.history_button.pack(fill='x', padx=10, pady=5)

        self.msg_label = tk.Label(root, text="", fg="red")
        self.msg_label.pack()

        self.update_display()

    def update_display(self, msg=None):
        s = f"Horloge vectorielle :\n{json.dumps(self.clock.to_dict(), indent=2)}"
        self.label.config(text=s)
        if msg:
            self.msg_label.config(text=msg)

    def local_event(self):
        self.clock.tick()
        self.update_display()

    def send_event(self, peer):
        self.clock.tick()
        self.network.send_to_peer(peer)
        self.update_display(f"📤 Horloge envoyée à {peer}")

    def save(self):
        save_local_state(self.clock)
        self.update_display("💾 État sauvegardé localement.")

    def show_history(self):
        top = tk.Toplevel()
        top.title("Historique des événements")
        txt = tk.Text(top, width=60, height=20)
        txt.pack()
        for event, clk in self.clock.history:
            txt.insert(tk.END, f"{event} : {clk}\n")

# ==========================
# LANCEMENT
# ==========================

if __name__ == "__main__":
    root = tk.Tk()
    app = ClockGUI(root)
    root.mainloop()
