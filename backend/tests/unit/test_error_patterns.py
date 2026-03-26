"""Unit tests for error pattern detection and fix application."""
from __future__ import annotations

import pytest

from src.executor.error_patterns import detect_error_pattern, apply_fix, get_fix_reason


# ---------------------------------------------------------------------------
# detect_error_pattern
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_detects_missing_python_module():
    name, info = await detect_error_pattern(
        stderr="ModuleNotFoundError: No module named 'requests'", stdout=""
    )
    assert name == "missing_dependency"
    assert info["package"] == "requests"


@pytest.mark.asyncio
async def test_detects_import_error():
    name, info = await detect_error_pattern(
        stderr="ImportError: No module named 'flask'", stdout=""
    )
    assert name == "missing_dependency"


@pytest.mark.asyncio
async def test_detects_permission_denied():
    name, info = await detect_error_pattern(
        stderr="Permission denied: /etc/hosts", stdout=""
    )
    assert name == "permission_denied"


@pytest.mark.asyncio
async def test_detects_port_in_use():
    name, info = await detect_error_pattern(
        stderr="Address already in use", stdout=""
    )
    assert name == "port_in_use"


@pytest.mark.asyncio
async def test_detects_eaddrinuse():
    name, info = await detect_error_pattern(
        stderr="Error: listen EADDRINUSE: address already in use :::3000", stdout=""
    )
    assert name == "port_in_use"


@pytest.mark.asyncio
async def test_detects_flask_async_missing():
    name, info = await detect_error_pattern(
        stderr="RuntimeError: Install Flask with the 'async' extra in order to use async views.",
        stdout="",
    )
    assert name == "flask_async_missing"


@pytest.mark.asyncio
async def test_detects_linker_not_found():
    name, info = await detect_error_pattern(
        stderr="error: linker `cc` not found", stdout=""
    )
    assert name == "linker_not_found"


@pytest.mark.asyncio
async def test_no_pattern_returns_none():
    name, info = await detect_error_pattern(
        stderr="some random output", stdout="all good"
    )
    assert name is None
    assert info == {}


@pytest.mark.asyncio
async def test_detects_npm_ci_fallback():
    name, info = await detect_error_pattern(
        stderr="npm ERR! package-lock.json not found", stdout=""
    )
    assert name == "npm_ci_fallback"


# ---------------------------------------------------------------------------
# apply_fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_fix_install_python_dependency():
    cmd = await apply_fix("install_dependency", "python app.py", {"package": "requests"})
    assert "pip install requests" in cmd
    assert "python app.py" in cmd


@pytest.mark.asyncio
async def test_apply_fix_install_npm_dependency():
    cmd = await apply_fix("install_dependency", "npm start", {"package": "express"})
    assert "npm install express" in cmd


@pytest.mark.asyncio
async def test_apply_fix_fix_permissions():
    cmd = await apply_fix("fix_permissions", "python app.py", {})
    assert "chmod" in cmd
    assert "python app.py" in cmd


@pytest.mark.asyncio
async def test_apply_fix_npm_install_fallback():
    cmd = await apply_fix("npm_install_fallback", "npm ci", {})
    assert cmd == "npm install"


@pytest.mark.asyncio
async def test_apply_fix_install_flask_async():
    cmd = await apply_fix("install_flask_async", "flask run", {})
    assert "flask[async]" in cmd
    assert "flask run" in cmd


@pytest.mark.asyncio
async def test_apply_fix_unknown_returns_none():
    cmd = await apply_fix("unknown_fix_type", "echo hello", {})
    assert cmd is None


@pytest.mark.asyncio
async def test_apply_fix_missing_package_returns_none():
    cmd = await apply_fix("install_dependency", "python app.py", {"package": None})
    assert cmd is None


# ---------------------------------------------------------------------------
# get_fix_reason
# ---------------------------------------------------------------------------


def test_get_fix_reason_missing_dependency():
    reason = get_fix_reason("missing_dependency", {"package": "requests"})
    assert "requests" in reason


def test_get_fix_reason_permission_denied():
    reason = get_fix_reason("permission_denied", {})
    assert "permission" in reason.lower()


def test_get_fix_reason_unknown_pattern():
    reason = get_fix_reason("some_unknown_pattern", {})
    assert "some_unknown_pattern" in reason
