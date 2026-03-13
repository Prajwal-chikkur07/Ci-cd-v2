import re
import socket

_PORT_CONFLICT_INDICATORS = [
    "Address already in use",
    "EADDRINUSE",
    "port is already allocated",
    "bind: address already in use",
    "address already in use",
]

_PORT_IN_COMMAND = re.compile(r":(\d{2,5})")


def detect_port_conflict(stderr: str) -> bool:
    """Check if the error indicates a port-in-use conflict."""
    return any(ind in stderr for ind in _PORT_CONFLICT_INDICATORS)


def find_free_port(preferred: int = 8000, range_size: int = 100) -> int:
    """Try preferred port first, then scan upward for a free one."""
    for port in [preferred] + list(range(preferred + 1, preferred + range_size)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {preferred}-{preferred + range_size}")


def extract_port_from_command(command: str) -> int | None:
    """Extract the first port-like number from a command string."""
    # Match patterns like -p 8080:8080, :8080, --port 8080, localhost:3000
    patterns = [
        re.compile(r"-p\s+(\d{2,5}):\d+"),
        re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):(\d{2,5})"),
        re.compile(r"--port[= ](\d{2,5})"),
        re.compile(r"-(?:p|P)\s+(\d{2,5})(?:\s|$)"),
        re.compile(r":(\d{4,5})"),
    ]
    for pattern in patterns:
        match = pattern.search(command)
        if match:
            return int(match.group(1))
    return None


def replace_port_in_command(command: str, old_port: int, new_port: int) -> str:
    """Replace all occurrences of old_port with new_port in a command."""
    return command.replace(str(old_port), str(new_port))
