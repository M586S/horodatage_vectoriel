class VectorClock:
    def __init__(self, node_id, all_nodes):
        self.node_id = node_id
        self.clock = {nid: 0 for nid in all_nodes}

    def increment(self):
        self.clock[self.node_id] += 1

    def update(self, received_clock):
        for node, ts in received_clock.items():
            self.clock[node] = max(self.clock[node], ts)
        self.increment()

    def happens_before(self, other_clock):
        return all(self.clock[k] <= other_clock[k] for k in self.clock) and any(self.clock[k] < other_clock[k] for k in self.clock)

    def to_dict(self):
        return self.clock.copy()

    def __repr__(self):
        return str(self.clock)
