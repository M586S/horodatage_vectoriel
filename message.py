import json

def create_message(sender, clock, key, value, msg_type="data", token=None):
    return json.dumps({
        "type": msg_type,
        "sender": sender,
        "clock": clock,
        "key": key,
        "value": value,
        "token": token
    }).encode()

def create_rename_message(old_id, new_id, token=None):
    return json.dumps({
        "type": "rename",
        "old_id": old_id,
        "new_id": new_id,
        "token": token
    }).encode()

def create_sync_request(sender, token=None):
    return json.dumps({
        "type": "sync_request",
        "sender": sender,
        "token": token
    }).encode()

def create_sync_response(sender, data, token=None):
    return json.dumps({
        "type": "sync_response",
        "sender": sender,
        "data": data,
        "token": token
    }).encode()

def parse_message(raw_data):
    return json.loads(raw_data.decode())