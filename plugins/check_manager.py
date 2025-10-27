#!/usr/bin/env python3
"""
Check Manager
Gestor de plugins de checks para monitorización
"""

import importlib
import inspect
import logging
from typing import Dict, Any, Optional, Type, Tuple
from pathlib import Path
from .checks.base import BaseCheck


class CheckManager:
    """Gestor de plugins de checks"""

    def __init__(self):
        self.logger = logging.getLogger('CheckManager')
        self.checks = {}
        self.logger.debug("Inicializando CheckManager...")
        self._load_builtin_checks()
        self._load_dynamic_checks()
        self.logger.info(f"CheckManager inicializado con {len(self.checks)} checks disponibles")

    def _load_builtin_checks(self):
        """Carga los checks incorporados"""
        self.logger.debug("Cargando checks incorporados...")
        builtin_checks = {
            'http': 'plugins.checks.http.HTTPCheck',
            'tcp': 'plugins.checks.tcp.TCPCheck',
            'docker': 'plugins.checks.docker.DockerCheck',
            'kubernetes': 'plugins.checks.kubernetes.KubernetesCheck',
            'prometheus': 'plugins.checks.prometheus.PrometheusCheck',
            'custom': 'plugins.checks.custom.CustomCheck'
        }

        for name, module_path in builtin_checks.items():
            try:
                self._load_check_class(name, module_path)
                self.logger.debug(f"Check incorporado cargado: {name}")
            except Exception as e:
                self.logger.error(f"Error cargando check incorporado {name}: {e}")

    def _load_dynamic_checks(self):
        """Carga checks dinámicamente desde el directorio plugins/checks"""
        self.logger.debug("Cargando checks dinámicos...")
        checks_dir = Path(__file__).parent / 'checks'
        if not checks_dir.exists():
            self.logger.warning(f"Directorio de checks no encontrado: {checks_dir}")
            return

        dynamic_checks_loaded = 0
        for py_file in checks_dir.glob('*.py'):
            if py_file.name.startswith('__'):
                continue  # Saltar __init__.py y similares

            module_name = f"plugins.checks.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                # Buscar clases que hereden de BaseCheck
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseCheck) and obj != BaseCheck:
                        # Usar el nombre de la clase en minúsculas como clave
                        check_name = name.lower().replace('check', '')
                        if check_name not in self.checks:  # Evitar sobrescribir built-ins
                            self.checks[check_name] = obj
                            self.logger.info(f"Check dinámico cargado: {check_name} desde {module_name}")
                            dynamic_checks_loaded += 1
                        else:
                            self.logger.debug(f"Check {check_name} ya existe, omitiendo versión dinámica")
            except Exception as e:
                self.logger.error(f"Error cargando check dinámico desde {module_name}: {e}")

        self.logger.debug(f"Checks dinámicos cargados: {dynamic_checks_loaded}")

    def _load_check_class(self, name: str, module_path: str):
        """Carga una clase de check desde un módulo"""
        module_name, class_name = module_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        check_class = getattr(module, class_name)

        if not issubclass(check_class, BaseCheck):
            raise ValueError(f"{class_name} no es una subclase de BaseCheck")

        self.checks[name] = check_class

    def get_check(self, protocol: str, config: Dict[str, Any]) -> Optional[BaseCheck]:
        """Obtiene una instancia de check para el protocolo dado"""
        protocol_lower = protocol.lower()
        self.logger.debug(f"Solicitando check para protocolo: {protocol_lower}")
        check_class = self.checks.get(protocol_lower)
        if not check_class:
            self.logger.warning(f"Protocolo no soportado: {protocol_lower}")
            return None

        try:
            instance = check_class(protocol, config)
            self.logger.debug(f"Instancia de check creada: {protocol_lower}")
            return instance
        except Exception as e:
            self.logger.error(f"Error creando instancia de check {protocol_lower}: {e}")
            return None

    def get_available_checks(self) -> list:
        """Retorna lista de checks disponibles"""
        return list(self.checks.keys())

    def validate_dependency_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida configuración de dependencia usando el check apropiado"""
        protocol = dependency_config.get('check_protocol', 'tcp')
        check_instance = self.get_check(protocol, {})

        if not check_instance:
            return False, f"Protocolo '{protocol}' no soportado"

        return check_instance.validate_config(dependency_config)

    def get_nagios_command(self, dependency_config: Dict[str, Any], host_address: str) -> str:
        """Genera comando de Nagios para una dependencia"""
        protocol = dependency_config.get('check_protocol', 'tcp')
        dep_name = dependency_config.get('name', 'unknown')
        self.logger.debug(f"Generando comando Nagios para {dep_name} (protocolo: {protocol}) en {host_address}")

        check_instance = self.get_check(protocol, {})

        if not check_instance:
            # Fallback a TCP básico
            port = dependency_config.get('port', 80)
            fallback_command = f"check_tcp -H {host_address} -p {port}"
            self.logger.warning(f"Usando comando fallback TCP para {dep_name}: {fallback_command}")
            return fallback_command

        # Enriquecer config con dirección del host
        enriched_config = dependency_config.copy()
        enriched_config['host_address'] = host_address

        try:
            command = check_instance.get_nagios_command(enriched_config)
            self.logger.debug(f"Comando generado para {dep_name}: {command}")
            return command
        except Exception as e:
            self.logger.error(f"Error generando comando para {dep_name}: {e}")
            # Fallback
            port = dependency_config.get('port', 80)
            return f"check_tcp -H {host_address} -p {port}"

    def get_required_params(self, protocol: str) -> list:
        """Obtiene parámetros requeridos para un protocolo"""
        check_instance = self.get_check(protocol, {})
        if not check_instance:
            return []
        return check_instance.get_required_params()

    def get_optional_params(self, protocol: str) -> list:
        """Obtiene parámetros opcionales para un protocolo"""
        check_instance = self.get_check(protocol, {})
        if not check_instance:
            return []
        return check_instance.get_optional_params()


# Instancia global del manager
check_manager = CheckManager()