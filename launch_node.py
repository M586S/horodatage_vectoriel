from multiprocessing import Process
import tkinter as tk
from app import NodeApp

def start_node(node_id, all_nodes, port, peers):
    root = tk.Tk()
    app = NodeApp(root, node_id, all_nodes, port, peers)
    root.mainloop()

if __name__ == '__main__':
    nodes = {
        'A': {'port': 5000, 'peers': [('localhost', 5001), ('localhost', 5002)]},
        'B': {'port': 5001, 'peers': [('localhost', 5000), ('localhost', 5002)]},
        'C': {'port': 5002, 'peers': [('localhost', 5000), ('localhost', 5001)]}
    }

    all_node_ids = list(nodes.keys())

    processes = []
    for node_id, config in nodes.items():
        p = Process(target=start_node, args=(node_id, all_node_ids, config['port'], config['peers']))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()
