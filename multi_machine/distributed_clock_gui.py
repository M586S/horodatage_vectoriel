import tkinter as tk
from tkinter import simpledialog, messagebox
import socket
import threading
import json
import time
import os

# --- Chargement de la configuration ---
CONFIG_FILE = 'config.json'
with open(CONFIG_FILE) as f:
    config = json.load(f)

NAME = config['name']
PORT = config['port']
PEERS = config['peers']  # {name: [ip, port]}
PASSWORD = config['password']

DATA_FILE = f"{NAME}_data.json"

# --- Horloge vectorielle ---
class VectorClock:
    def __init__(self, peers):
        self.clock = {peer: 0 for peer in peers}
        self.clock[NAME] = 0

    def increment(self):
        self.clock[NAME] += 1

    def update(self, received):
        for k in received:
            self.clock[k] = max(self.clock.get(k, 0), received[k])
        self.increment()

    def get(self):
        return dict(self.clock)

# --- Persistance ---
def save_state(history, clock):
    with open(DATA_FILE, 'w') as f:
        json.dump({
            'history': history,
            'clock': clock.get()
        }, f)

def load_state():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            data = json.load(f)
            return data['history'], data['clock']
    return [], {}

# --- Envoi réseau sécurisé ---
def send_to_peer(peer_name, message_data):
    ip, port = PEERS[peer_name]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((ip, port))
            s.sendall(json.dumps(message_data).encode())
    except:
        print(f"⚠️ Peer {peer_name} injoignable")

# --- Réception réseau ---
def server_thread():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(('', PORT))
        server.listen()
        print(f"[{NAME}] En attente sur le port {PORT}...")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn,)).start()

def handle_client(conn):
    with conn:
        data = conn.recv(4096).decode()
        try:
            message = json.loads(data)
        except:
            return

        # Authentification
        if message.get('password') != PASSWORD:
            print("🔒 Authentification échouée.")
            return

        sender = message['sender']
        text = message['text']
        remote_clock = message['clock']

        clock.update(remote_clock)
        history.append((sender, text, clock.get()))
        save_state(history, clock)
        update_gui()

# --- GUI ---
def send_message():
    text = input_field.get()
    if not text:
        return

    clock.increment()
    history.append((NAME, text, clock.get()))
    save_state(history, clock)
    update_gui()

    for peer in PEERS:
        send_to_peer(peer, {
            'sender': NAME,
            'text': text,
            'clock': clock.get(),
            'password': PASSWORD
        })
    input_field.delete(0, tk.END)

def update_gui():
    text_display.config(state=tk.NORMAL)
    text_display.delete(1.0, tk.END)
    for sender, text, clk in history:
        text_display.insert(tk.END, f"[{sender}] {text} {clk}\n")
    text_display.config(state=tk.DISABLED)

# --- Initialisation ---
history, saved_clock = load_state()
clock = VectorClock(list(PEERS.keys()))
if saved_clock:
    clock.clock.update(saved_clock)

# --- Démarrage serveur ---
threading.Thread(target=server_thread, daemon=True).start()

# --- Interface graphique ---
root = tk.Tk()
root.title(f"Horloge Vectorielle - {NAME}")

text_display = tk.Text(root, state=tk.DISABLED, width=60, height=20)
text_display.pack(padx=10, pady=10)

input_field = tk.Entry(root, width=50)
input_field.pack(side=tk.LEFT, padx=(10, 0), pady=(0, 10))

send_button = tk.Button(root, text="Envoyer", command=send_message)
send_button.pack(side=tk.LEFT, padx=10, pady=(0, 10))

update_gui()
root.mainloop()
