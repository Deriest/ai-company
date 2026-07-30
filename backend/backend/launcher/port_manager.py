import socket
import logging

logger = logging.getLogger(__name__)

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def find_free_port(start_port: int = 8000, max_port: int = 8099, host: str = "127.0.0.1") -> int:
    for port in range(start_port, max_port + 1):
        if not is_port_in_use(port, host):
            return port
    raise RuntimeError(f"No free ports found in range {start_port}-{max_port}")
