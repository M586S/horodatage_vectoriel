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
