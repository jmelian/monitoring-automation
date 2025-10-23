#!/usr/bin/env python3
"""
HTTP Check Plugin
Plugin para verificaciones HTTP/HTTPS
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class HTTPCheck(BaseCheck):
    """Plugin para checks HTTP/HTTPS"""

    def get_required_params(self) -> list:
        return ['port']

    def get_optional_params(self) -> list:
        return ['url', 'expected_status', 'timeout', 'auth_user', 'auth_pass', 'ssl']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración HTTP"""
        port = dependency_config.get('port')
        if not port:
            return False, "Puerto requerido para check HTTP"

        if not isinstance(port, int) and not str(port).isdigit():
            return False, "Puerto debe ser numérico"

        url = dependency_config.get('check_params', {}).get('url', '/')
        if not url.startswith('/'):
            return False, "URL debe comenzar con /"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para HTTP"""
        host_address = dependency_config.get('host_address', '')
        port = dependency_config.get('port', 80)
        check_params = dependency_config.get('check_params', {})

        # Comando base
        cmd_parts = [f"check_http -H {host_address} -p {port}"]

        # URL específica
        url = check_params.get('url', '/')
        if url != '/':
            cmd_parts.append(f"-u {url}")

        # Status esperado
        expected_status = check_params.get('expected_status', 200)
        if expected_status != 200:
            cmd_parts.append(f"-e {expected_status}")

        # Timeout
        timeout = check_params.get('timeout', self.get_default_timeout())
        if timeout != self.get_default_timeout():
            cmd_parts.append(f"-t {timeout}")

        # Autenticación
        auth_user = check_params.get('auth_user')
        auth_pass = check_params.get('auth_pass')
        if auth_user and auth_pass:
            cmd_parts.append(f"-a {auth_user}:{auth_pass}")

        # SSL
        ssl = check_params.get('ssl', False)
        if ssl:
            cmd_parts.append("-S")

        return " ".join(cmd_parts)