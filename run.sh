#!/bin/bash

# Terminal 1
gnome-terminal -- bash -c "python3 node.py A 5000 B:5001,C:5002"

# Terminal 2
gnome-terminal -- bash -c "python3 node.py B 5001 A:5000,C:5002"

# Terminal 3
gnome-terminal -- bash -c "python3 node.py C 5002 A:5000,B:5001"
