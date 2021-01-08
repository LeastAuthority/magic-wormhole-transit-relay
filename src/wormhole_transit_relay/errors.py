from collections import namedtuple


class CrowdedError(Exception):
    pass
class ReclaimedError(Exception):
    pass

SidedMessage = namedtuple("SidedMessage", ["side", "phase", "body",
                                           "server_rx", "msg_id"])
