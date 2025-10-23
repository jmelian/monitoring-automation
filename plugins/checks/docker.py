#!/usr/bin/env python3
"""
Docker Check Plugin
Plugin para verificaciones de contenedores Docker
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class DockerCheck(BaseCheck):
    """Plugin para checks de contenedores Docker"""

    def get_required_params(self) -> list:
        return ['container_name']

    def get_optional_params(self) -> list:
        return ['check_type', 'timeout', 'socket_path', 'cpu_threshold', 'memory_threshold', 'disk_threshold']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración Docker"""
        check_params = dependency_config.get('check_params', {})
        container_name = check_params.get('container_name')

        if not container_name:
            return False, "Nombre de contenedor requerido"

        check_type = check_params.get('check_type', 'running')
        valid_types = ['running', 'status', 'health', 'cpu', 'memory', 'disk', 'logs']

        if check_type not in valid_types:
            return False, f"Tipo de check inválido. Válidos: {', '.join(valid_types)}"

        # Validar thresholds para métricas
        if check_type in ['cpu', 'memory', 'disk']:
            threshold = check_params.get(f'{check_type}_threshold')
            if threshold is None:
                return False, f"Threshold requerido para check de {check_type}"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para Docker"""
        check_params = dependency_config.get('check_params', {})
        container_name = check_params.get('container_name')
        check_type = check_params.get('check_type', 'running')
        socket_path = check_params.get('socket_path', '/var/run/docker.sock')

        # Comando personalizado que debe existir en Nagios
        cmd_parts = [f"check_docker -c {container_name} -t {check_type}"]

        # Socket personalizado
        if socket_path != '/var/run/docker.sock':
            cmd_parts.append(f"-s {socket_path}")

        # Thresholds para métricas
        if check_type == 'cpu':
            threshold = check_params.get('cpu_threshold', 80)
            cmd_parts.append(f"-w {threshold} -c {threshold + 10}")
        elif check_type == 'memory':
            threshold = check_params.get('memory_threshold', 80)
            cmd_parts.append(f"-w {threshold} -c {threshold + 10}")
        elif check_type == 'disk':
            threshold = check_params.get('disk_threshold', 80)
            cmd_parts.append(f"-w {threshold} -c {threshold + 10}")

        # Timeout
        timeout = check_params.get('timeout', self.get_default_timeout())
        if timeout != self.get_default_timeout():
            cmd_parts.append(f"-T {timeout}")

        return " ".join(cmd_parts)