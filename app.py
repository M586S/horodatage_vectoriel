import tkinter as tk
from tkinter import ttk, messagebox
import threading
import socket
from vector_clock import VectorClock
from message import create_message, parse_message

class NodeApp:
    def __init__(self, root, node_id, all_nodes, port, peers):
        self.root = root
        self.node_id = node_id
        self.vc = VectorClock(node_id, all_nodes)
        self.data = {}
        self.port = port
        self.peers = peers  # [(host, port)]
        
        self.setup_ui()
        threading.Thread(target=self.listen, daemon=True).start()

    def setup_ui(self):
        self.root.title(f"Nœud {self.node_id}")
        
        self.key_entry = ttk.Entry(self.root, width=15)
        self.key_entry.grid(row=0, column=0, padx=5, pady=5)
        
        self.value_entry = ttk.Entry(self.root, width=15)
        self.value_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Button(self.root, text="Enregistrer", command=self.set_key).grid(row=0, column=2, padx=5)
        
        self.clock_label = ttk.Label(self.root, text="Horloge vectorielle : {}".format(self.vc))
        self.clock_label.grid(row=1, column=0, columnspan=3, pady=5)
        
        self.data_display = tk.Text(self.root, height=10, width=50)
        self.data_display.grid(row=2, column=0, columnspan=3, padx=5, pady=5)

    def refresh_ui(self):
        self.clock_label.config(text="Horloge vectorielle : {}".format(self.vc))
        self.data_display.delete("1.0", tk.END)
        for k, v in self.data.items():
            self.data_display.insert(tk.END, f"{k} = {v['value']}  |  horloge: {v['clock']}\n")

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
            messagebox.showwarning("Conflit détecté", f"Conflit sur la clé '{key}' avec le nœud {sender}. Valeur : {value}")
            self.data[key] = {"value": value, "clock": clock}
        else:
            self.vc.update(clock)
            self.data[key] = {"value": value, "clock": clock}
        self.refresh_ui()

    def happens_after(self, c1, c2):
        return all(c1[k] >= c2[k] for k in c1) and any(c1[k] > c2[k] for k in c1)

    def set_key(self):
        key = self.key_entry.get()
        value = self.value_entry.get()
        if not key or not value:
            return
        self.vc.increment()
        clock = self.vc.to_dict()
        self.data[key] = {"value": value, "clock": clock}
        self.refresh_ui()
        msg = create_message(self.node_id, clock, key, value)
        for host, port in self.peers:
            self.send_message(host, port, msg)

    def send_message(self, host, port, msg):
        try:
            s = socket.socket()
            s.connect((host, port))
            s.send(msg)
            s.close()
        except:
            print(f"[{self.node_id}] ❌ Erreur envoi vers {host}:{port}")
