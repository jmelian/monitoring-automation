#!/usr/bin/env python3
"""
TCP Check Plugin
Plugin para verificaciones TCP
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class TCPCheck(BaseCheck):
    """Plugin para checks TCP"""

    def get_required_params(self) -> list:
        return ['port']

    def get_optional_params(self) -> list:
        return ['timeout', 'send', 'expect', 'ssl']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración TCP"""
        port = dependency_config.get('port')
        if not port:
            return False, "Puerto requerido para check TCP"

        if not isinstance(port, int) and not str(port).isdigit():
            return False, "Puerto debe ser numérico"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para TCP"""
        host_address = dependency_config.get('host_address', '')
        port = dependency_config.get('port')
        check_params = dependency_config.get('check_params', {})

        # Comando base
        cmd_parts = [f"check_tcp -H {host_address} -p {port}"]

        # Timeout
        timeout = check_params.get('timeout', self.get_default_timeout())
        if timeout != self.get_default_timeout():
            cmd_parts.append(f"-t {timeout}")

        # String a enviar
        send = check_params.get('send')
        if send:
            cmd_parts.append(f"-s '{send}'")

        # String esperada como respuesta
        expect = check_params.get('expect')
        if expect:
            cmd_parts.append(f"-e '{expect}'")

        # SSL
        ssl = check_params.get('ssl', False)
        if ssl:
            cmd_parts.append("-S")

        return " ".join(cmd_parts)