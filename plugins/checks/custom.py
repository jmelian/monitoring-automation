#!/usr/bin/env python3
"""
Custom Check Plugin
Plugin para verificaciones personalizadas
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class CustomCheck(BaseCheck):
    """Plugin para checks personalizados"""

    def get_required_params(self) -> list:
        return ['command']

    def get_optional_params(self) -> list:
        return ['args', 'timeout', 'working_directory']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración custom"""
        check_params = dependency_config.get('check_params', {})
        command = check_params.get('command')

        if not command:
            return False, "Comando requerido para check custom"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para check custom"""
        check_params = dependency_config.get('check_params', {})
        command = check_params.get('command')
        args = check_params.get('args', [])
        timeout = check_params.get('timeout', self.get_default_timeout())
        working_dir = check_params.get('working_directory', '')

        # Comando personalizado
        cmd_parts = [f"check_custom_command -c '{command}'"]

        if args:
            if isinstance(args, list):
                args_str = " ".join(str(arg) for arg in args)
            else:
                args_str = str(args)
            cmd_parts.append(f"-a '{args_str}'")

        if timeout != self.get_default_timeout():
            cmd_parts.append(f"-t {timeout}")

        if working_dir:
            cmd_parts.append(f"-d '{working_dir}'")

        return " ".join(cmd_parts)