#!/usr/bin/env python3
"""
Base class for check plugins
Clase base para plugins de verificación
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
import logging


class BaseCheck(ABC):
    """Clase base para todos los plugins de checks"""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f'check.{name}')

    @abstractmethod
    def get_nagios_command(self, dependency_config: Dict[str, Any]) -> str:
        """
        Genera el comando de Nagios para este check

        Args:
            dependency_config: Configuración de la dependencia desde JSON

        Returns:
            Comando de Nagios completo
        """
        pass

    @abstractmethod
    def validate_config(self, dependency_config: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida que la configuración sea correcta

        Args:
            dependency_config: Configuración a validar

        Returns:
            (válido, mensaje_error)
        """
        pass

    @abstractmethod
    def get_required_params(self) -> list:
        """
        Retorna lista de parámetros requeridos para este check

        Returns:
            Lista de nombres de parámetros obligatorios
        """
        pass

    def get_optional_params(self) -> list:
        """
        Retorna lista de parámetros opcionales

        Returns:
            Lista de nombres de parámetros opcionales
        """
        return []

    def format_command_params(self, params: Dict[str, Any]) -> str:
        """
        Formatea parámetros para comando de Nagios

        Args:
            params: Diccionario de parámetros

        Returns:
            String formateado para comando
        """
        formatted = []
        for key, value in params.items():
            if isinstance(value, bool):
                if value:
                    formatted.append(f"-{key}")
            elif isinstance(value, (int, float)):
                formatted.append(f"-{key} {value}")
            else:
                formatted.append(f"-{key} {value}")
        return " ".join(formatted)

    def get_default_timeout(self) -> int:
        """Timeout por defecto en segundos"""
        return 30

    def get_default_interval(self) -> int:
        """Intervalo por defecto en segundos"""
        return 300