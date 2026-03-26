"""Unit tests for error pattern detection and fix application."""

import pytest
from src.executor.error_patterns import detect_error_pattern, apply_fix, get_fix_reason


class TestErrorPatternDetection:
    """Test error pattern detection."""
    
    @pytest.mark.asyncio
    async def test_detect_missing_python_module(self):
        """Test detection of missing Python module."""
        stderr = "ModuleNotFoundError: No module named 'requests'"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "missing_dependency"
        assert info["fix_type"] == "install_dependency"
        assert info["package"] == "requests"
    
    @pytest.mark.asyncio
    async def test_detect_permission_denied(self):
        """Test detection of permission denied error."""
        stderr = "Permission denied: /app/script.sh"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "permission_denied"
        assert info["fix_type"] == "fix_permissions"
    
    @pytest.mark.asyncio
    async def test_detect_port_in_use(self):
        """Test detection of port already in use."""
        stderr = "Address already in use: 0.0.0.0:3000"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "port_in_use"
        assert info["fix_type"] == "use_different_port"
    
    @pytest.mark.asyncio
    async def test_detect_eaddrinuse(self):
        """Test detection of EADDRINUSE error."""
        stderr = "Error: listen EADDRINUSE: address already in use :::3000"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "port_in_use"
        assert info["fix_type"] == "use_different_port"
    
    @pytest.mark.asyncio
    async def test_detect_wrong_entry_point(self):
        """Test detection of wrong entry point."""
        stderr = "ERROR: Flask app entry point not found"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "wrong_entry_point"
        assert info["fix_type"] == "try_alternative_entry_point"
    
    @pytest.mark.asyncio
    async def test_detect_npm_ci_fallback(self):
        """Test detection of npm ci failure."""
        stderr = "npm ci ENOENT: no such file or directory"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "npm_ci_fallback"
        assert info["fix_type"] == "npm_install_fallback"
    
    @pytest.mark.asyncio
    async def test_detect_linker_not_found(self):
        """Test detection of linker not found."""
        stderr = "error: linker `cc` not found"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "linker_not_found"
        assert info["fix_type"] == "install_build_tools"
    
    @pytest.mark.asyncio
    async def test_detect_flask_async_missing(self):
        """Test detection of Flask async extra missing."""
        stderr = "RuntimeError: Install Flask with the 'async' extra"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name == "flask_async_missing"
        assert info["fix_type"] == "install_flask_async"
    
    @pytest.mark.asyncio
    async def test_no_pattern_match(self):
        """Test when no pattern matches."""
        stderr = "Some random error that doesn't match any pattern"
        pattern_name, info = await detect_error_pattern(stderr, "")
        
        assert pattern_name is None
        assert info == {}
    
    @pytest.mark.asyncio
    async def test_detect_in_stdout(self):
        """Test detection in stdout instead of stderr."""
        stdout = "ModuleNotFoundError: No module named 'numpy'"
        pattern_name, info = await detect_error_pattern("", stdout)
        
        assert pattern_name == "missing_dependency"
        assert info["package"] == "numpy"


class TestApplyFix:
    """Test fix application."""
    
    @pytest.mark.asyncio
    async def test_apply_pip_install_fix(self):
        """Test applying pip install fix."""
        command = "python app.py"
        match_info = {"package": "requests"}
        
        fixed = await apply_fix("install_dependency", command, match_info)
        
        assert fixed == "pip install requests && python app.py"
    
    @pytest.mark.asyncio
    async def test_apply_npm_install_fix(self):
        """Test applying npm install fix."""
        command = "npm start"
        match_info = {"package": "express"}
        
        fixed = await apply_fix("install_dependency", command, match_info)
        
        assert fixed == "npm install express && npm start"
    
    @pytest.mark.asyncio
    async def test_apply_permission_fix(self):
        """Test applying permission fix."""
        command = "./script.sh"
        
        fixed = await apply_fix("fix_permissions", command, {})
        
        assert fixed == "chmod -R 755 . && ./script.sh"
    
    @pytest.mark.asyncio
    async def test_apply_npm_ci_fallback(self):
        """Test applying npm ci fallback fix."""
        command = "npm ci && npm start"
        
        fixed = await apply_fix("npm_install_fallback", command, {})
        
        assert fixed == "npm install && npm start"
    
    @pytest.mark.asyncio
    async def test_apply_build_tools_fix(self):
        """Test applying build tools fix."""
        command = "cargo build"
        
        fixed = await apply_fix("install_build_tools", command, {})
        
        assert "build-essential" in fixed
        assert "cargo build" in fixed
    
    @pytest.mark.asyncio
    async def test_apply_flask_async_fix(self):
        """Test applying Flask async fix."""
        command = "python app.py"
        
        fixed = await apply_fix("install_flask_async", command, {})
        
        assert fixed == "pip install 'flask[async]' && python app.py"
    
    @pytest.mark.asyncio
    async def test_apply_fix_with_missing_package(self):
        """Test applying fix when package info is missing."""
        command = "python app.py"
        match_info = {}
        
        fixed = await apply_fix("install_dependency", command, match_info)
        
        assert fixed is None
    
    @pytest.mark.asyncio
    async def test_apply_unknown_fix_type(self):
        """Test applying unknown fix type."""
        command = "python app.py"
        
        fixed = await apply_fix("unknown_fix", command, {})
        
        assert fixed is None


class TestFixReason:
    """Test fix reason generation."""
    
    def test_missing_dependency_reason(self):
        """Test reason for missing dependency."""
        reason = get_fix_reason("missing_dependency", {"package": "requests"})
        
        assert "requests" in reason
        assert "install" in reason.lower()
    
    def test_permission_denied_reason(self):
        """Test reason for permission denied."""
        reason = get_fix_reason("permission_denied", {})
        
        assert "permission" in reason.lower()
    
    def test_port_in_use_reason(self):
        """Test reason for port in use."""
        reason = get_fix_reason("port_in_use", {"port": "3000"})
        
        assert "3000" in reason
        assert "port" in reason.lower()
    
    def test_wrong_entry_point_reason(self):
        """Test reason for wrong entry point."""
        reason = get_fix_reason("wrong_entry_point", {})
        
        assert "entry point" in reason.lower()
    
    def test_npm_ci_fallback_reason(self):
        """Test reason for npm ci fallback."""
        reason = get_fix_reason("npm_ci_fallback", {})
        
        assert "npm" in reason.lower()
    
    def test_linker_not_found_reason(self):
        """Test reason for linker not found."""
        reason = get_fix_reason("linker_not_found", {})
        
        assert "linker" in reason.lower() or "build" in reason.lower()
    
    def test_flask_async_reason(self):
        """Test reason for Flask async missing."""
        reason = get_fix_reason("flask_async_missing", {})
        
        assert "flask" in reason.lower() or "async" in reason.lower()
