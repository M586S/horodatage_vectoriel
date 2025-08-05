import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import json
import os

CONFIG_FILE = "config.json"

# --- Vector Clock ---
class VectorClock:
    def __init__(self, node_id, all_nodes):
        self.node_id = node_id
        self.clock = {nid: 0 for nid in all_nodes}

    def increment(self):
        self.clock[self.node_id] += 1

    def update(self, received_clock):
        for node, ts in received_clock.items():
            self.clock[node] = max(self.clock.get(node, 0), ts)
        self.increment()

    def rename_node(self, old_id, new_id):
        if old_id in self.clock:
            self.clock[new_id] = self.clock.pop(old_id)
        else:
            self.clock[new_id] = 0
        if self.node_id == old_id:
            self.node_id = new_id

    def happens_before(self, other_clock):
        return all(self.clock.get(k, 0) <= other_clock.get(k, 0) for k in other_clock) and any(self.clock.get(k, 0) < other_clock.get(k, 0) for k in other_clock)

    def to_dict(self):
        return self.clock.copy()

    def __repr__(self):
        return str(self.clock)

# --- Message creation/parsing ---
def create_message(sender, clock, key, value, msg_type="data", password=None):
    return json.dumps({
        "type": msg_type,
        "sender": sender,
        "clock": clock,
        "key": key,
        "value": value,
        "password": password
    }).encode()

def create_rename_message(old_id, new_id, password=None):
    return json.dumps({
        "type": "rename",
        "old_id": old_id,
        "new_id": new_id,
        "password": password
    }).encode()

def create_conflict_resolution_message(sender, key, value, clock, password=None):
    return json.dumps({
        "type": "conflict_resolution",
        "sender": sender,
        "key": key,
        "value": value,
        "clock": clock,
        "password": password
    }).encode()

def parse_message(raw_data):
    return json.loads(raw_data.decode())

# --- Main App ---
class NodeApp:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        self.node_id = self.config.get("node_id", "Node")
        self.password = self.config.get("password", "secret")
        self.peers = self.config.get("peers", {})  # dict: name -> [ip, port]
        self.port = self.config.get("port", 5000)

        self.all_nodes = list(self.peers.keys()) + [self.node_id]
        self.vc = VectorClock(self.node_id, self.all_nodes)
        self.data = {}

        self.conflict_windows = {}  # Ajouté : dictionnaire pour gérer les fenêtres de conflit ouvertes

        self.setup_ui()
        threading.Thread(target=self.listen, daemon=True).start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                return json.load(f)
        # default config
        return {
            "node_id": "Node",
            "port": 5000,
            "password": "secret",
            "peers": {}
        }

    def save_config(self):
        self.config["node_id"] = self.node_id
        self.config["port"] = self.port
        self.config["password"] = self.password
        self.config["peers"] = self.peers
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def setup_ui(self):
        self.root.title(f"Nœud {self.node_id}")
        self.root.geometry("700x500")
        self.root.resizable(False, False)

        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True)

        # --- Tab 1: Data Management ---
        self.tab_data = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_data, text="Données")

        frm_input = ttk.Frame(self.tab_data)
        frm_input.pack(pady=10, padx=10)

        ttk.Label(frm_input, text="Clé :").grid(row=0, column=0, padx=5)
        self.key_entry = ttk.Entry(frm_input, width=15)
        self.key_entry.grid(row=0, column=1, padx=5)

        ttk.Label(frm_input, text="Valeur :").grid(row=0, column=2, padx=5)
        self.value_entry = ttk.Entry(frm_input, width=15)
        self.value_entry.grid(row=0, column=3, padx=5)

        ttk.Button(frm_input, text="Enregistrer", command=self.set_key).grid(row=0, column=4, padx=10)
        ttk.Button(frm_input, text="Synchroniser", command=self.broadcast_data).grid(row=0, column=5)

        self.clock_label = ttk.Label(self.tab_data, text="", font=("Courier", 10))
        self.clock_label.pack(pady=5)

        frm_data = ttk.LabelFrame(self.tab_data, text="Données stockées", padding=(10, 5))
        frm_data.pack(fill="both", expand=True, padx=10, pady=5)

        self.data_display = tk.Text(frm_data, height=10, wrap="none", bg="#f0f0f0")
        self.data_display.pack(fill="both", expand=True)

        frm_log = ttk.LabelFrame(self.tab_data, text="Journal des événements", padding=(10, 5))
        frm_log.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_display = tk.Text(frm_log, height=7, wrap="word", bg="#fff8dc", fg="black")
        self.log_display.pack(fill="both", expand=True)

        # --- Tab 2: Configuration ---
        self.tab_config = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_config, text="Configuration")

        # Node rename
        frm_rename = ttk.LabelFrame(self.tab_config, text="Renommer le nœud", padding=(10,10))
        frm_rename.pack(fill="x", padx=10, pady=10)
        self.rename_entry = ttk.Entry(frm_rename, width=25)
        self.rename_entry.insert(0, self.node_id)
        self.rename_entry.pack(side="left", padx=(0,10))
        ttk.Button(frm_rename, text="Renommer", command=self.rename_node_ui).pack(side="left")

        # Password
        frm_password = ttk.LabelFrame(self.tab_config, text="Mot de passe d'authentification", padding=(10,10))
        frm_password.pack(fill="x", padx=10, pady=10)
        self.pass_entry = ttk.Entry(frm_password, show="*", width=25)
        self.pass_entry.insert(0, self.password)
        self.pass_entry.pack(side="left", padx=(0,10))
        ttk.Button(frm_password, text="Modifier", command=self.change_password).pack(side="left")

        # Peers list
        frm_peers = ttk.LabelFrame(self.tab_config, text="Pairs (Peers)", padding=(10,10))
        frm_peers.pack(fill="both", expand=True, padx=10, pady=10)

        self.peers_tree = ttk.Treeview(frm_peers, columns=("IP", "Port"), show="headings", selectmode="browse")
        self.peers_tree.heading("IP", text="Adresse IP")
        self.peers_tree.heading("Port", text="Port")
        self.peers_tree.pack(fill="both", expand=True, side="left")

        # Scrollbar peers
        scrollbar = ttk.Scrollbar(frm_peers, orient="vertical", command=self.peers_tree.yview)
        self.peers_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="left", fill="y")

        # Buttons for peers
        frm_peer_buttons = ttk.Frame(frm_peers)
        frm_peer_buttons.pack(side="left", fill="y", padx=10)

        ttk.Button(frm_peer_buttons, text="Ajouter", command=self.add_peer).pack(fill="x", pady=5)
        ttk.Button(frm_peer_buttons, text="Modifier", command=self.edit_peer).pack(fill="x", pady=5)
        ttk.Button(frm_peer_buttons, text="Supprimer", command=self.remove_peer).pack(fill="x", pady=5)

        self.refresh_peers_ui()
        self.refresh_ui()

    # ========== DATA TAB ===========
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
        s.bind(('', self.port))  # écoute sur toutes interfaces
        s.listen()
        while True:
            conn, _ = s.accept()
            threading.Thread(target=self.handle_connection, args=(conn,), daemon=True).start()

    def handle_connection(self, conn):
        with conn:
            data = conn.recv(4096)
            if not data:
                return
            try:
                msg = parse_message(data)
            except:
                return
            # Auth
            if msg.get("password") != self.password:
                self.log_event(f"🔒 Authentification échouée de {msg.get('sender')}", "red")
                return

            if msg.get("type") == "rename":
                old_id = msg["old_id"]
                new_id = msg["new_id"]
                self.vc.rename_node(old_id, new_id)
                if old_id == self.node_id:
                    self.node_id = new_id
                    self.config["node_id"] = new_id
                    self.root.title(f"Nœud {self.node_id}")
                    self.rename_entry.delete(0, tk.END)
                    self.rename_entry.insert(0, new_id)
                self.log_event(f"🔄 Nœud renommé (reçu) : {old_id} → {new_id}", "purple")
                self.refresh_ui()
                self.save_config()
                return

            elif msg.get("type") == "conflict_resolution":
                key = msg["key"]
                value = msg["value"]
                clock = msg["clock"]
                self.data[key] = {"value": value, "clock": clock}
                self.log_event(f"🛠️ Conflit résolu à distance : {key} = {value}", "purple")
                self.refresh_ui()
                return

            # Type "data"
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
                # Fenêtre modale pour choix utilisateur (bloquante)
                choice = self.ask_user_conflict(
                    key,
                    self.data[key]["value"], self.data[key]["clock"],
                    value, clock
                )
                if choice == "local":
                    self.log_event(f"⚠️ Conflit sur '{key}': conservé localement.", "orange")
                    # Propager la résolution locale à pairs (forcer à garder local)
                    res_msg = create_conflict_resolution_message(self.node_id, key,
                        self.data[key]["value"], self.data[key]["clock"], password=self.password)
                else:
                    self.data[key] = {"value": value, "clock": clock}
                    self.log_event(f"⚠️ Conflit sur '{key}': remplacé par la version distante.", "red")
                    res_msg = create_conflict_resolution_message(self.node_id, key, value, clock, password=self.password)

                self.refresh_ui()

                # Propager la résolution aux pairs
                for peer_name, (host, port) in self.peers.items():
                    self.send_message(host, port, res_msg)

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

        msg = create_message(self.node_id, clock, key, value, msg_type="data", password=self.password)
        for peer_name, (host, port) in self.peers.items():
            self.send_message(host, port, msg)

    def broadcast_data(self):
        for key, val in self.data.items():
            msg = create_message(self.node_id, val["clock"], key, val["value"], msg_type="data", password=self.password)
            for peer_name, (host, port) in self.peers.items():
                self.send_message(host, port, msg)
        self.log_event("🔁 Synchronisation forcée avec les pairs", "purple")

    def send_message(self, host, port, msg):
        try:
            s = socket.socket()
            s.settimeout(5)
            s.connect((host, port))
            s.send(msg)
            s.close()
        except Exception as e:
            self.log_event(f"❌ Erreur d'envoi vers {host}:{port} ({e})", "gray")

    # ========== CONFIG TAB ===========
    def refresh_peers_ui(self):
        self.peers_tree.delete(*self.peers_tree.get_children())
        for name, (ip, port) in self.peers.items():
            self.peers_tree.insert("", "end", iid=name, values=(ip, port))

    def add_peer(self):
        dlg = PeerDialog(self.root, "Ajouter un pair")
        if dlg.result:
            name, ip, port = dlg.result
            if name in self.peers:
                messagebox.showerror("Erreur", "Ce nom de pair existe déjà.")
                return
            self.peers[name] = (ip, int(port))
            self.all_nodes = list(self.peers.keys()) + [self.node_id]
            self.vc.clock = {nid: self.vc.clock.get(nid, 0) for nid in self.all_nodes}
            self.save_config()
            self.refresh_peers_ui()

    def edit_peer(self):
        selected = self.peers_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Veuillez sélectionner un pair.")
            return
        name = selected[0]
        ip, port = self.peers[name]
        dlg = PeerDialog(self.root, "Modifier un pair", name, ip, port)
        if dlg.result:
            new_name, new_ip, new_port = dlg.result
            if new_name != name and new_name in self.peers:
                messagebox.showerror("Erreur", "Ce nom de pair existe déjà.")
                return
            del self.peers[name]
            self.peers[new_name] = (new_ip, int(new_port))
            self.all_nodes = list(self.peers.keys()) + [self.node_id]
            self.vc.clock = {nid: self.vc.clock.get(nid, 0) for nid in self.all_nodes}
            self.save_config()
            self.refresh_peers_ui()

    def remove_peer(self):
        selected = self.peers_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Veuillez sélectionner un pair.")
            return
        name = selected[0]
        if messagebox.askyesno("Confirmation", f"Supprimer le pair '{name}' ?"):
            del self.peers[name]
            self.all_nodes = list(self.peers.keys()) + [self.node_id]
            self.vc.clock = {nid: self.vc.clock.get(nid, 0) for nid in self.all_nodes}
            self.save_config()
            self.refresh_peers_ui()

    def rename_node_ui(self):
        new_name = self.rename_entry.get().strip()
        if not new_name:
            messagebox.showinfo("Erreur", "Le nom du nœud ne peut pas être vide.")
            self.rename_entry.delete(0, tk.END)
            self.rename_entry.insert(0, self.node_id)
            return
        if new_name == self.node_id:
            messagebox.showinfo("Info", "Le nom du nœud est déjà ce nom.")
            return

        old_id = self.node_id
        self.node_id = new_name
        self.vc.rename_node(old_id, new_name)
        self.root.title(f"Nœud {self.node_id}")
        self.log_event(f"🔧 Nom modifié localement : {old_id} → {new_name}", "blue")
        self.save_config()
        self.refresh_ui()

        # Informer les pairs
        msg = create_rename_message(old_id, new_name, password=self.password)
        for peer_name, (host, port) in self.peers.items():
            self.send_message(host, port, msg)

    # --- Fenêtre modale pour conflit ---
    def ask_user_conflict(self, key, local_value, local_clock, remote_value, remote_clock):
        # Fermeture de toutes les autres fenêtres conflit ouvertes dès qu'un choix est fait
        if key in self.conflict_windows:
            existing_win = self.conflict_windows[key]
            existing_win.lift()
            self.root.wait_window(existing_win)
            existing_win.destroy()
            del self.conflict_windows[key]

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Conflit détecté sur '{key}'")

        ttk.Label(dlg, text="Valeur locale :").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(dlg, text=f"{local_value} (horloge: {local_clock})", foreground="blue").pack(anchor="w", padx=20)

        ttk.Label(dlg, text="Valeur distante :").pack(anchor="w", padx=10, pady=(10, 0))
        ttk.Label(dlg, text=f"{remote_value} (horloge: {remote_clock})", foreground="green").pack(anchor="w", padx=20)

        choice = tk.StringVar(value="")

        def close_all_conflict_windows():
            for k, win in list(self.conflict_windows.items()):
                if win is not dlg:
                    win.destroy()
                    del self.conflict_windows[k]

        def keep_local():
            choice.set("local")
            close_all_conflict_windows()
            dlg.destroy()

        def keep_remote():
            choice.set("remote")
            close_all_conflict_windows()
            dlg.destroy()

        frm_buttons = ttk.Frame(dlg)
        frm_buttons.pack(pady=15)
        ttk.Button(frm_buttons, text="Garder local", command=keep_local).pack(side="left", padx=10)
        ttk.Button(frm_buttons, text="Garder distant", command=keep_remote).pack(side="right", padx=10)

        dlg.grab_set()
        self.conflict_windows[key] = dlg
        self.root.wait_window(dlg)

        if key in self.conflict_windows:
            del self.conflict_windows[key]

        return choice.get()
    
    # --- Modifier mot de passe ---
    def change_password(self):
        new_pass = self.pass_entry.get().strip()
        if not new_pass:
            messagebox.showinfo("Erreur", "Le mot de passe ne peut pas être vide.")
            self.pass_entry.delete(0, tk.END)
            self.pass_entry.insert(0, self.password)
            return
        if new_pass == self.password:
            messagebox.showinfo("Info", "Le mot de passe est déjà celui-ci.")
            return
        self.password = new_pass
        self.log_event("🔐 Mot de passe modifié localement.", "blue")
        messagebox.showinfo("Info", "Mot de passe modifié localement.")
        self.save_config()

# --- Fenêtre modale pour ajouter/modifier un peer ---
class PeerDialog(simpledialog.Dialog):
    def __init__(self, parent, title, name="", ip="", port=""):
        self.name = name
        self.ip = ip
        self.port = port
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Nom :").grid(row=0, column=0, sticky="e")
        self.e_name = ttk.Entry(master)
        self.e_name.grid(row=0, column=1)
        self.e_name.insert(0, self.name)

        ttk.Label(master, text="Adresse IP :").grid(row=1, column=0, sticky="e")
        self.e_ip = ttk.Entry(master)
        self.e_ip.grid(row=1, column=1)
        self.e_ip.insert(0, self.ip)

        ttk.Label(master, text="Port :").grid(row=2, column=0, sticky="e")
        self.e_port = ttk.Entry(master)
        self.e_port.grid(row=2, column=1)
        self.e_port.insert(0, self.port)

        return self.e_name

    def validate(self):
        name = self.e_name.get().strip()
        ip = self.e_ip.get().strip()
        port = self.e_port.get().strip()
        if not name or not ip or not port:
            messagebox.showerror("Erreur", "Tous les champs sont requis.")
            return False
        try:
            int(port)
        except:
            messagebox.showerror("Erreur", "Le port doit être un nombre entier.")
            return False
        return True

    def apply(self):
        self.result = (self.e_name.get().strip(), self.e_ip.get().strip(), self.e_port.get().strip())

if __name__ == "__main__":
    root = tk.Tk()
    app = NodeApp(root)
    root.mainloop()
