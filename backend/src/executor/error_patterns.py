"""Error pattern detection and automated fix application."""

import logging
import re
from dataclasses import dataclass
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ErrorPattern:
    """Represents a detectable error pattern and its fix strategy."""
    name: str
    patterns: list[str]  # Regex patterns to match
    fix_type: str  # Type of fix to apply
    extract_info: Optional[Callable[[re.Match], dict]] = None  # Extract info from match


# Define all error patterns
ERROR_PATTERNS = [
    ErrorPattern(
        name="missing_dependency",
        patterns=[
            r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
            r"ImportError: No module named ['\"]([^'\"]+)['\"]",
            r"cannot find -l(\w+)",
            r"package ['\"]([^'\"]+)['\"] not found",
            r"npm ERR! code ERESOLVE",
            r"npm ERR! ERESOLVE unable to resolve dependency tree",
        ],
        fix_type="install_dependency",
        extract_info=lambda m: {"package": m.group(1) if m.lastindex and m.lastindex >= 1 else None},
    ),
    ErrorPattern(
        name="permission_denied",
        patterns=[
            r"Permission denied",
            r"EACCES: permission denied",
            r"permission denied \(publickey\)",
        ],
        fix_type="fix_permissions",
    ),
    ErrorPattern(
        name="port_in_use",
        patterns=[
            r"Address already in use",
            r"EADDRINUSE",
            r"port (\d+) is already in use",
        ],
        fix_type="use_different_port",
        extract_info=lambda m: {"port": m.group(1) if m.lastindex and m.lastindex >= 1 else None},
    ),
    ErrorPattern(
        name="wrong_entry_point",
        patterns=[
            r"ERROR: Flask app entry point not found",
            r"Cannot find module",
            r"No such file or directory.*app\.py",
            r"ModuleNotFoundError: No module named '__main__'",
        ],
        fix_type="try_alternative_entry_point",
    ),
    ErrorPattern(
        name="npm_ci_fallback",
        patterns=[
            r"npm ci.*ENOENT",
            r"npm ci.*No such file",
            r"npm warn",
        ],
        fix_type="npm_install_fallback",
    ),
    ErrorPattern(
        name="linker_not_found",
        patterns=[
            r"linker `cc` not found",
            r"linker not found",
            r"error: linker",
        ],
        fix_type="install_build_tools",
    ),
    ErrorPattern(
        name="flask_async_missing",
        patterns=[
            r"RuntimeError: Install Flask with the 'async' extra",
        ],
        fix_type="install_flask_async",
    ),
]


async def detect_error_pattern(stderr: str, stdout: str) -> tuple[Optional[str], dict]:
    """
    Detect error pattern in command output.
    
    Returns:
        Tuple of (pattern_name, match_info) or (None, {}) if no pattern matches
    """
    combined = (stderr or "") + (stdout or "")
    
    for pattern in ERROR_PATTERNS:
        for regex in pattern.patterns:
            try:
                match = re.search(regex, combined, re.IGNORECASE)
                if match:
                    info = {
                        "pattern_name": pattern.name,
                        "fix_type": pattern.fix_type,
                        "match": match,
                    }
                    if pattern.extract_info:
                        try:
                            extracted = pattern.extract_info(match)
                            info.update(extracted)
                        except Exception as e:
                            logger.warning(f"Failed to extract info from pattern {pattern.name}: {e}")
                    
                    logger.info(f"Detected error pattern: {pattern.name}")
                    return pattern.name, info
            except re.error as e:
                logger.error(f"Invalid regex pattern {regex}: {e}")
                continue
    
    return None, {}


async def apply_fix(fix_type: str, command: str, match_info: dict) -> Optional[str]:
    """
    Apply fix to command based on fix type.
    
    Returns:
        Modified command or None if fix cannot be applied
    """
    if fix_type == "install_dependency":
        package = match_info.get("package")
        if not package:
            logger.warning("Cannot extract package name for dependency fix")
            return None
        
        # Determine package manager from command
        if "python" in command or "pip" in command:
            return f"pip install {package} && {command}"
        elif "npm" in command or "yarn" in command:
            return f"npm install {package} && {command}"
        elif "cargo" in command:
            return f"cargo add {package} && {command}"
        else:
            # Default to pip
            return f"pip install {package} && {command}"
    
    elif fix_type == "fix_permissions":
        return f"chmod -R 755 . && {command}"
    
    elif fix_type == "use_different_port":
        # This is handled at a higher level in dispatcher
        # Just return the command as-is for now
        logger.info("Port conflict detected - will be handled by dispatcher")
        return None
    
    elif fix_type == "try_alternative_entry_point":
        # Try different entry points for Flask/Python apps
        alternatives = ["app.py", "wsgi.py", "application.py", "main.py"]
        for alt in alternatives:
            if alt not in command:
                modified = command.replace("app.py", alt)
                if modified != command:
                    return modified
        return None
    
    elif fix_type == "npm_install_fallback":
        # Fallback from npm ci to npm install
        if "npm ci" in command:
            return command.replace("npm ci", "npm install")
        return None
    
    elif fix_type == "install_build_tools":
        # Install build tools for C/Rust compilation
        return f"apt-get update && apt-get install -y build-essential 2>/dev/null || true && {command}"
    
    elif fix_type == "install_flask_async":
        # Install Flask with async extra
        return f"pip install 'flask[async]' && {command}"
    
    else:
        logger.warning(f"Unknown fix type: {fix_type}")
        return None


def get_fix_reason(pattern_name: str, match_info: dict) -> str:
    """Generate human-readable reason for the fix."""
    if pattern_name == "missing_dependency":
        package = match_info.get("package", "unknown")
        return f"Missing dependency: {package}. Attempting to install."
    elif pattern_name == "permission_denied":
        return "Permission denied. Fixing permissions and retrying."
    elif pattern_name == "port_in_use":
        port = match_info.get("port", "unknown")
        return f"Port {port} is already in use. Will retry on different port."
    elif pattern_name == "wrong_entry_point":
        return "Wrong entry point detected. Trying alternative entry points."
    elif pattern_name == "npm_ci_fallback":
        return "npm ci failed. Falling back to npm install."
    elif pattern_name == "linker_not_found":
        return "C linker not found. Installing build-essential."
    elif pattern_name == "flask_async_missing":
        return "Flask async support missing. Installing flask[async]."
    else:
        return f"Detected error pattern: {pattern_name}. Applying fix."
