import json


def dict_to_bytes(d):
    assert isinstance(d, dict)
    b = json.dumps(d).encode("utf-8")
    assert isinstance(b, type(b""))
    return b
def bytes_to_dict(b):
    assert isinstance(b, type(b""))
    d = json.loads(b.decode("utf-8"))
    assert isinstance(d, dict)
    return d
