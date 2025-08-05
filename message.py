import json

def create_message(sender, clock, key, value, msg_type="data"):
    return json.dumps({
        "type": msg_type,
        "sender": sender,
        "clock": clock,
        "key": key,
        "value": value
    }).encode()

def create_rename_message(old_id, new_id):
    return json.dumps({
        "type": "rename",
        "old_id": old_id,
        "new_id": new_id
    }).encode()

def parse_message(raw_data):
    return json.loads(raw_data.decode())
