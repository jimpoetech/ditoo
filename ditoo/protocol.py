"""Divoom Ditoo low-level packet framing and Bluetooth transport."""

import socket
import time


def build_packet(command, args=None):
    """Build a framed Divoom protocol packet.

    Packet format: 0x01 [len_lo len_hi cmd args...] [crc_lo crc_hi] 0x02
    Length covers: 2 (length field) + 1 (cmd) + len(args)
    Checksum: sum of all frame_body bytes, masked to 16 bits.
    """
    if args is None:
        args = []
    payload_len = len(args) + 3
    size_lo = payload_len & 0xFF
    size_hi = (payload_len >> 8) & 0xFF
    frame_body = [size_lo, size_hi, command] + list(args)
    checksum = sum(frame_body) & 0xFFFF
    return bytes([0x01] + frame_body + [checksum & 0xFF, (checksum >> 8) & 0xFF, 0x02])


def chunk_payload(args, chunk_size=200):
    """Split a large argument list into chunks for animation commands.

    Each chunk is at most chunk_size bytes (200 bytes = 400 hex chars).
    Returns list of byte lists.
    """
    chunks = []
    for i in range(0, len(args), chunk_size):
        chunks.append(args[i:i + chunk_size])
    return chunks


class BluetoothTransport:
    """Bluetooth RFCOMM connection to a Divoom device."""

    def __init__(self, mac_address, port=2, connect_timeout=10):
        self.mac = mac_address
        self.port = port
        self.connect_timeout = connect_timeout
        self.sock = None

    @property
    def connected(self):
        return self.sock is not None

    def connect(self):
        """Establish Bluetooth RFCOMM connection."""
        self.sock = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
        )
        self.sock.settimeout(self.connect_timeout)
        self.sock.connect((self.mac, self.port))
        self.sock.settimeout(None)
        time.sleep(1)

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, packet):
        """Send raw bytes. Raises ConnectionError if not connected."""
        if not self.sock:
            raise ConnectionError("Not connected")
        self.sock.send(packet)

    def receive(self, bufsize=1024, timeout=2):
        """Try to receive a response. Returns bytes or None on timeout."""
        if not self.sock:
            return None
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(bufsize)
        except socket.timeout:
            return None
        finally:
            self.sock.settimeout(None)

    def send_command(self, command, args=None):
        """Build and send a single command packet."""
        self.send(build_packet(command, args))
