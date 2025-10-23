#!/usr/bin/env python3
"""
Prometheus Check Plugin
Plugin para métricas de Prometheus
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class PrometheusCheck(BaseCheck):
    """Plugin para checks de métricas Prometheus"""

    def get_required_params(self) -> list:
        return ['query']

    def get_optional_params(self) -> list:
        return ['prometheus_url', 'threshold_warning', 'threshold_critical', 'comparison']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración Prometheus"""
        check_params = dependency_config.get('check_params', {})
        query = check_params.get('query')

        if not query:
            return False, "Query de Prometheus requerida"

        comparison = check_params.get('comparison', '>')
        valid_comparisons = ['>', '<', '>=', '<=', '==', '!=']
        if comparison not in valid_comparisons:
            return False, f"Comparación inválida. Válidas: {', '.join(valid_comparisons)}"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para Prometheus"""
        check_params = dependency_config.get('check_params', {})
        query = check_params.get('query')
        prometheus_url = check_params.get('prometheus_url', 'http://localhost:9090')
        threshold_warning = check_params.get('threshold_warning', 80)
        threshold_critical = check_params.get('threshold_critical', 90)
        comparison = check_params.get('comparison', '>')

        # Comando personalizado para Prometheus
        cmd_parts = [
            f"check_prometheus_metric",
            f"-u {prometheus_url}",
            f"-q '{query}'",
            f"-w {threshold_warning}",
            f"-c {threshold_critical}",
            f"-o {comparison}"
        ]

        return " ".join(cmd_parts)