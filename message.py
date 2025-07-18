import json

def create_message(sender, clock, key, value):
    return json.dumps({
        "sender": sender,
        "clock": clock,
        "key": key,
        "value": value
    }).encode()

def parse_message(raw_data):
    return json.loads(raw_data.decode())
