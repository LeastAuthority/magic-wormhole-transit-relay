from __future__ import unicode_literals
import signal

from twisted.internet import reactor
from twisted.python import log
from autobahn.twisted import websocket

from .transit_server import TransitConnection, Transit

# The WebSocket allows the client to send "commands" to the server, and the
# server to send "responses" to the client. Note that commands and responses
# are not necessarily one-to-one. All commands provoke an "ack" response
# (with a copy of the original message) for timing, testing, and
# synchronization purposes. All commands and responses are JSON-encoded.

# Each WebSocket connection is bound to one "appid" and one "side", which are
# set by the "bind" command (which must be the first command on the
# connection), and must be set before any other command will be accepted.

# Each connection can be bound to a single "mailbox" (a two-sided
# store-and-forward queue, identified by the "mailbox id": a long, randomly
# unique string identifier) by using the "open" command. This protects the
# mailbox from idle closure, enables the "add" command (to put new messages
# in the queue), and triggers delivery of past and future messages via the
# "message" response. The "close" command removes the binding (but note that
# it does not enable the subsequent binding of a second mailbox). When the
# last side closes a mailbox, its contents are deleted.

# Additionally, the connection can be bound a single "nameplate", which is
# short identifier that makes up the first component of a wormhole code. Each
# nameplate points to a single long-id "mailbox". The "allocate" message
# determines the shortest available numeric nameplate, reserves it, and
# returns the nameplate id. "list" returns a list of all numeric nameplates
# which currently have only one side active (i.e. they are waiting for a
# partner). The "claim" message reserves an arbitrary nameplate id (perhaps
# the receiver of a wormhole connection typed in a code they got from the
# sender, or perhaps the two sides agreed upon a code offline and are both
# typing it in), and the "release" message releases it. When every side that
# has claimed the nameplate has also released it, the nameplate is
# deallocated (but they will probably keep the underlying mailbox open).

# "claim" and "release" may only be called once per connection, however calls
# across connections (assuming a consistent "side") are idempotent. [connect,
# claim, disconnect, connect, claim] is legal, but not useful, as is a
# "release" for a nameplate that nobody is currently claiming.

# "open" and "close" may only be called once per connection. They are
# basically idempotent, however "open" doubles as a subscribe action. So
# [connect, open, disconnect, connect, open] is legal *and* useful (without
# the second "open", the second connection would not be subscribed to hear
# about new messages).

# Inbound (client to server) commands are marked as "->" below. Unrecognized
# inbound keys will be ignored. Outbound (server to client) responses use
# "<-". There is no guaranteed correlation between requests and responses. In
# this list, "A -> B" means that some time after A is received, at least one
# message of type B will be sent out (probably).

# All responses include a "server_tx" key, which is a float (seconds since
# epoch) with the server clock just before the outbound response was written
# to the socket.

# connection -> welcome
#  <- {type: "welcome", welcome: {}} # .welcome keys are all optional:
#        current_cli_version: out-of-date clients display a warning
#        motd: all clients display message, then continue normally
#        error: all clients display mesage, then terminate with error
# -> {type: "bind", appid:, side:}
#
# -> {type: "list"} -> nameplates
#  <- {type: "nameplates", nameplates: [{id: str,..},..]}
# -> {type: "allocate"} -> nameplate, mailbox
#  <- {type: "allocated", nameplate: str}
# -> {type: "claim", nameplate: str} -> mailbox
#  <- {type: "claimed", mailbox: str}
# -> {type: "release"}
#     .nameplate is optional, but must match previous claim()
#  <- {type: "released"}
#
# -> {type: "open", mailbox: str} -> message
#     sends old messages now, and subscribes to deliver future messages
#  <- {type: "message", side:, phase:, body:, msg_id:}} # body is hex
# -> {type: "add", phase: str, body: hex} # will send echo in a "message"
#
# -> {type: "close", mood: str} -> closed
#     .mailbox is optional, but must match previous open()
#  <- {type: "closed"}
#
#  <- {type: "error", error: str, orig: {}} # in response to malformed msgs

# for tests that need to know when a message has been processed:
# -> {type: "ping", ping: int} -> pong (does not require bind/claim)
#  <- {type: "pong", pong: int}

class Error(Exception):
    def __init__(self, explain):
        self._explain = explain

class WebSocketTransit(websocket.WebSocketServerProtocol, TransitConnection):
    def __init__(self):
        websocket.WebSocketServerProtocol.__init__(self)
        TransitConnection.__init__(self)
        # self._handshake_done = False

    def onMessage(self, payload, isBinary):
        log.msg(f'onMesage payload: #{payload}; isBinary #{isBinary}')

        if not self._sent_ok:
            log.msg('not _sent_ok calling lineReceived')
            self.lineReceived(payload)
        else:
            log.msg('_sent_ok calling rawDataReceived')
            TransitConnection.rawDataReceived(self, payload)

    def sendLine(self, data):
        # log.msg(f'self.transport: #{self.transport}')
        log.msg(f'sendData: #{data}')
        # signal.raise_signal(signal.SIGUSR2)
        self.sendMessage(data, True)

    # def sendData(self, data, *args):
    #     log.msg(f'_sendData: #{data}')
    #     websocket.WebSocketServerProtocol.sendData(self, data, *args)


class WebSocketTransitFactory(websocket.WebSocketServerFactory, Transit):
    protocol = WebSocketTransit

    def __init__(self, url, server, blur_usage, log_file, usage_db):
        websocket.WebSocketServerFactory.__init__(self, url)
        Transit.__init__(self, blur_usage, log_file, usage_db)
        self.setProtocolOptions(autoPingInterval=60, autoPingTimeout=600)
        self.server = server
        self.reactor = reactor # for tests to control
