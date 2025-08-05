import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import socket
from vector_clock import VectorClock
from message import create_message, create_rename_message, parse_message

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
        self.root.geometry("600x450")
        self.root.resizable(False, False)

        frm_input = ttk.Frame(self.root)
        frm_input.pack(pady=10)

        ttk.Label(frm_input, text="Clé :").grid(row=0, column=0, padx=5)
        self.key_entry = ttk.Entry(frm_input, width=15)
        self.key_entry.grid(row=0, column=1, padx=5)

        ttk.Label(frm_input, text="Valeur :").grid(row=0, column=2, padx=5)
        self.value_entry = ttk.Entry(frm_input, width=15)
        self.value_entry.grid(row=0, column=3, padx=5)

        ttk.Button(frm_input, text="Enregistrer", command=self.set_key).grid(row=0, column=4, padx=10)
        ttk.Button(frm_input, text="Synchroniser", command=self.broadcast_data).grid(row=0, column=5)
        ttk.Button(frm_input, text="📝 Renommer", command=self.rename_node).grid(row=0, column=6, padx=5)

        self.clock_label = ttk.Label(self.root, text="", font=("Courier", 10))
        self.clock_label.pack(pady=5)

        frm_data = ttk.LabelFrame(self.root, text="Données stockées", padding=(10, 5))
        frm_data.pack(fill="both", expand=True, padx=10, pady=5)

        self.data_display = tk.Text(frm_data, height=8, wrap="none", bg="#f0f0f0")
        self.data_display.pack(fill="both", expand=True)

        frm_log = ttk.LabelFrame(self.root, text="Journal des événements", padding=(10, 5))
        frm_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_display = tk.Text(frm_log, height=6, wrap="word", bg="#fff8dc", fg="black")
        self.log_display.pack(fill="both", expand=True)

        self.refresh_ui()

    def refresh_ui(self):
        self.clock_label.config(text=f"🕒 Horloge vectorielle locale : {self.vc}")
        self.data_display.delete("1.0", tk.END)
        for k, v in self.data.items():
            val = v['value']
            clock = v['clock']
            self.data_display.insert(tk.END, f"{k:<10} = {val:<10}  |  horloge: {clock}\n")

    def log_event(self, msg, color="black"):
        self.log_display.insert(tk.END, f"{msg}\n", ("tag",))
        self.log_display.tag_config("tag", foreground=color)
        self.log_display.see(tk.END)

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
        if msg.get("type") == "rename":
            old_id = msg["old_id"]
            new_id = msg["new_id"]
            self.vc.rename_node(old_id, new_id)
            self.log_event(f"🔄 Nœud renommé (reçu) : {old_id} → {new_id}", "purple")
            self.refresh_ui()
            return

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
            self.log_event(f"⚠️ Conflit sur '{key}' avec {sender}. Remplacement par la version reçue.", "red")
            messagebox.showwarning("Conflit détecté", f"Conflit sur la clé '{key}' avec {sender}")
            self.data[key] = {"value": value, "clock": clock}
        else:
            self.vc.update(clock)
            self.data[key] = {"value": value, "clock": clock}
            self.log_event(f"✅ Donnée reçue : {key} = {value} de {sender}", "green")

        self.refresh_ui()

    def happens_after(self, c1, c2):
        return all(c1.get(k, 0) >= c2.get(k, 0) for k in c1) and any(c1.get(k, 0) > c2.get(k, 0) for k in c1)


    def set_key(self):
        key = self.key_entry.get().strip()
        value = self.value_entry.get().strip()
        if not key or not value:
            messagebox.showinfo("Entrée invalide", "Veuillez remplir les deux champs.")
            return
        self.vc.increment()
        clock = self.vc.to_dict()
        self.data[key] = {"value": value, "clock": clock}
        self.log_event(f"📤 Mise à jour locale : {key} = {value}", "blue")
        self.refresh_ui()

        msg = create_message(self.node_id, clock, key, value, msg_type="data")
        for host, port in self.peers:
            self.send_message(host, port, msg)

    def broadcast_data(self):
        for key, val in self.data.items():
            msg = create_message(self.node_id, val["clock"], key, val["value"], msg_type="data")
            for host, port in self.peers:
                self.send_message(host, port, msg)
        self.log_event("🔁 Synchronisation forcée avec les pairs", "purple")

    def rename_node(self):
        new_id = simpledialog.askstring("Renommer le nœud", "Nouveau nom du nœud :")
        if new_id and new_id.strip() and new_id != self.node_id:
            old_id = self.node_id
            new_id = new_id.strip()

            self.node_id = new_id
            self.vc.rename_node(old_id, new_id)
            self.root.title(f"Nœud {self.node_id}")
            self.refresh_ui()
            self.log_event(f"🔧 Nom modifié localement : {old_id} → {new_id}", "blue")

            msg = create_rename_message(old_id, new_id)
            for host, port in self.peers:
                self.send_message(host, port, msg)
        else:
            messagebox.showinfo("Renommage", "Aucun changement effectué.")

    def send_message(self, host, port, msg):
        try:
            s = socket.socket()
            s.connect((host, port))
            s.send(msg)
            s.close()
        except:
            self.log_event(f"❌ Erreur d'envoi vers {host}:{port}", "gray")
