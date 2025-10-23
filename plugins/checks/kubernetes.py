#!/usr/bin/env python3
"""
Kubernetes Check Plugin
Plugin para verificaciones de Kubernetes
"""

from typing import Dict, Any, Tuple
from .base import BaseCheck


class KubernetesCheck(BaseCheck):
    """Plugin para checks de Kubernetes"""

    def get_required_params(self) -> list:
        return ['resource_type']

    def get_optional_params(self) -> list:
        return ['namespace', 'resource_name', 'check_type', 'kubeconfig', 'cpu_threshold', 'memory_threshold', 'replicas_min']

    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración Kubernetes"""
        check_params = dependency_config.get('check_params', {})
        resource_type = check_params.get('resource_type')

        if not resource_type:
            return False, "Tipo de recurso requerido (pod, deployment, service)"

        valid_types = ['pod', 'deployment', 'service', 'daemonset', 'statefulset']
        if resource_type not in valid_types:
            return False, f"Tipo de recurso inválido. Válidos: {', '.join(valid_types)}"

        check_type = check_params.get('check_type', 'status')
        valid_checks = ['status', 'ready', 'available', 'replicas', 'cpu', 'memory']
        if check_type not in valid_checks:
            return False, f"Tipo de check inválido. Válidos: {', '.join(valid_checks)}"

        # Validar thresholds para métricas
        if check_type in ['cpu', 'memory']:
            threshold = check_params.get(f'{check_type}_threshold')
            if threshold is None:
                return False, f"Threshold requerido para check de {check_type}"
        elif check_type == 'replicas':
            replicas_min = check_params.get('replicas_min')
            if replicas_min is None:
                return False, "Número mínimo de replicas requerido"

        return True, ""

    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """Genera comando Nagios para Kubernetes"""
        check_params = dependency_config.get('check_params', {})
        resource_type = check_params.get('resource_type')
        resource_name = check_params.get('resource_name', '')
        namespace = check_params.get('namespace', 'default')
        check_type = check_params.get('check_type', 'status')
        kubeconfig = check_params.get('kubeconfig', '~/.kube/config')

        # Comando personalizado para Kubernetes
        cmd_parts = [f"check_kubernetes -t {resource_type} -n {namespace} -c {check_type}"]

        if resource_name:
            cmd_parts.append(f"-r {resource_name}")

        # Thresholds para métricas
        if check_type == 'cpu':
            threshold = check_params.get('cpu_threshold', 80)
            cmd_parts.append(f"-w {threshold} -c {threshold + 10}")
        elif check_type == 'memory':
            threshold = check_params.get('memory_threshold', 80)
            cmd_parts.append(f"-w {threshold} -c {threshold + 10}")
        elif check_type == 'replicas':
            replicas_min = check_params.get('replicas_min', 1)
            cmd_parts.append(f"-m {replicas_min}")

        if kubeconfig != '~/.kube/config':
            cmd_parts.append(f"-k {kubeconfig}")

        return " ".join(cmd_parts)