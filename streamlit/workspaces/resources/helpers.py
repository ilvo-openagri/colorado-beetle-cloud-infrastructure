import socket
from contextlib import closing


def check_remote_port(host: str, port: int) -> bool:
    """Verify if a port is open an a server

    Args:
        host (str): The server (IP address or DNS name)
        port (int): Port

    Returns:
        bool: Port is open on the server?
    """
    port_open = False
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(2)
        connection = sock.connect_ex((host, port))
        sock.settimeout(None)
        port_open = connection == 0
    return port_open
