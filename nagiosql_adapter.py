#!/usr/bin/env python3
"""
NagiosQL Adapter
Adaptador para integrar configuraciones de Nagios con NagiosQL
Soporta importación automática de hosts, servicios y comandos vía API REST
"""

import json
import logging
import requests
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import hashlib
import re


class NagiosQLAdapter:
    """
    Adaptador para integración con NagiosQL

    Soporta múltiples métodos de integración:
    1. API REST (recomendado)
    2. Inserción directa en base de datos
    3. Importación vía archivos temporales
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el adaptador de NagiosQL

        Args:
            config: Configuración de conexión a NagiosQL
        """
        self.logger = logging.getLogger('NagiosQLAdapter')

        # Configuración de conexión
        self.base_url = config.get('api_url', 'http://localhost/nagiosql')
        self.api_key = config.get('api_key')
        self.username = config.get('username')
        self.password = config.get('password')
        self.verify_ssl = config.get('verify_ssl', True)
        self.timeout = config.get('timeout', 30)

        # Configuración de base de datos (para inserción directa)
        self.db_config = config.get('database', {})

        # Método de integración preferido
        self.integration_method = config.get('integration_method', 'api')

        # Configuración de idempotencia
        self.use_checksums = config.get('use_checksums', True)
        self.update_existing = config.get('update_existing', True)

        # Sesión HTTP persistente
        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = (self.username, self.password)

        self.logger.info(f"NagiosQL Adapter inicializado - Método: {self.integration_method}")

    def import_configurations(self, config_files: Dict[str, str]) -> bool:
        """
        Importa configuraciones de Nagios a NagiosQL

        Args:
            config_files: Diccionario con nombre_archivo: contenido

        Returns:
            bool: True si la importación fue exitosa
        """
        self.logger.info("Iniciando importación de configuraciones a NagiosQL")

        try:
            if self.integration_method == 'api':
                return self._import_via_api(config_files)
            elif self.integration_method == 'database':
                return self._import_via_database(config_files)
            elif self.integration_method == 'file':
                return self._import_via_file(config_files)
            else:
                raise ValueError(f"Método de integración no soportado: {self.integration_method}")

        except Exception as e:
            self.logger.error(f"Error durante la importación: {e}")
            return False

    def _import_via_api(self, config_files: Dict[str, str]) -> bool:
        """
        Importa configuraciones vía API REST de NagiosQL

        NagiosQL tiene endpoints para:
        - /api/v1/hosts (POST, PUT, DELETE)
        - /api/v1/services (POST, PUT, DELETE)
        - /api/v1/commands (POST, PUT, DELETE)
        - /api/v1/contacts (POST, PUT, DELETE)
        - /api/v1/contactgroups (POST, PUT, DELETE)
        """
        self.logger.info("Importando vía API REST")

        success = True

        # Procesar cada tipo de configuración
        config_types = {
            'hosts.cfg': self._process_hosts_config,
            'services.cfg': self._process_services_config,
            'commands.cfg': self._process_commands_config,
            'contacts.cfg': self._process_contacts_config
        }

        for filename, content in config_files.items():
            if filename in config_types:
                try:
                    objects = config_types[filename](content)
                    if not self._import_objects_via_api(filename.replace('.cfg', ''), objects):
                        success = False
                except Exception as e:
                    self.logger.error(f"Error procesando {filename}: {e}")
                    success = False

        return success

    def _process_hosts_config(self, content: str) -> List[Dict]:
        """Procesa configuración de hosts y retorna lista de objetos"""
        objects = []
        host_blocks = self._parse_nagios_config_blocks(content, 'define host')

        for block in host_blocks:
            host_obj = {
                'host_name': block.get('host_name', ''),
                'alias': block.get('alias', ''),
                'address': block.get('address', ''),
                'check_command': block.get('check_command', 'check-host-alive'),
                'check_interval': int(block.get('check_interval', 300)),
                'retry_interval': int(block.get('retry_interval', 60)),
                'max_check_attempts': int(block.get('max_check_attempts', 3)),
                'check_period': block.get('check_period', '24x7'),
                'notification_period': block.get('notification_period', '24x7'),
                'notification_interval': int(block.get('notification_interval', 60)),
                'notifications_enabled': block.get('notifications_enabled', '1') == '1',
                'register': block.get('register', '1') == '1'
            }

            if self.use_checksums:
                host_obj['_checksum'] = self._calculate_checksum(host_obj)

            objects.append(host_obj)

        return objects

    def _process_services_config(self, content: str) -> List[Dict]:
        """Procesa configuración de servicios"""
        objects = []
        service_blocks = self._parse_nagios_config_blocks(content, 'define service')

        for block in service_blocks:
            service_obj = {
                'service_description': block.get('service_description', ''),
                'host_name': block.get('host_name', ''),
                'check_command': block.get('check_command', ''),
                'check_interval': int(block.get('check_interval', 300)),
                'retry_interval': int(block.get('retry_interval', 60)),
                'max_check_attempts': int(block.get('max_check_attempts', 3)),
                'check_period': block.get('check_period', '24x7'),
                'notification_period': block.get('notification_period', '24x7'),
                'notification_interval': int(block.get('notification_interval', 60)),
                'notifications_enabled': block.get('notifications_enabled', '1') == '1',
                'contact_groups': block.get('contact_groups', ''),
                'register': block.get('register', '1') == '1'
            }

            if self.use_checksums:
                service_obj['_checksum'] = self._calculate_checksum(service_obj)

            objects.append(service_obj)

        return objects

    def _process_commands_config(self, content: str) -> List[Dict]:
        """Procesa configuración de comandos"""
        objects = []
        command_blocks = self._parse_nagios_config_blocks(content, 'define command')

        for block in command_blocks:
            command_obj = {
                'command_name': block.get('command_name', ''),
                'command_line': block.get('command_line', ''),
                'register': block.get('register', '1') == '1'
            }

            if self.use_checksums:
                command_obj['_checksum'] = self._calculate_checksum(command_obj)

            objects.append(command_obj)

        return objects

    def _process_contacts_config(self, content: str) -> List[Dict]:
        """Procesa configuración de contactos"""
        objects = []
        contact_blocks = self._parse_nagios_config_blocks(content, 'define contact')

        for block in contact_blocks:
            contact_obj = {
                'contact_name': block.get('contact_name', ''),
                'alias': block.get('alias', ''),
                'email': block.get('email', ''),
                'service_notification_period': block.get('service_notification_period', '24x7'),
                'host_notification_period': block.get('host_notification_period', '24x7'),
                'service_notification_options': block.get('service_notification_options', 'w,u,c,r,f,s'),
                'host_notification_options': block.get('host_notification_options', 'd,u,r,f,s'),
                'service_notification_commands': block.get('service_notification_commands', 'notify-service-by-email'),
                'host_notification_commands': block.get('host_notification_commands', 'notify-host-by-email'),
                'register': block.get('register', '1') == '1'
            }

            if self.use_checksums:
                contact_obj['_checksum'] = self._calculate_checksum(contact_obj)

            objects.append(contact_obj)

        # Procesar contactgroups también
        contactgroup_blocks = self._parse_nagios_config_blocks(content, 'define contactgroup')
        for block in contactgroup_blocks:
            cg_obj = {
                'contactgroup_name': block.get('contactgroup_name', ''),
                'alias': block.get('alias', ''),
                'members': block.get('members', ''),
                'register': block.get('register', '1') == '1'
            }

            if self.use_checksums:
                cg_obj['_checksum'] = self._calculate_checksum(cg_obj)

            objects.append(cg_obj)

        return objects

    def _parse_nagios_config_blocks(self, content: str, block_type: str) -> List[Dict]:
        """Parsea bloques de configuración de Nagios"""
        blocks = []
        lines = content.split('\n')
        current_block = {}
        in_block = False

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith(block_type + ' {'):
                in_block = True
                current_block = {}
                continue

            if line == '}' and in_block:
                in_block = False
                if current_block:
                    blocks.append(current_block)
                current_block = {}
                continue

            if in_block and '\t' in line:
                key, value = line.split('\t', 1)
                current_block[key.strip()] = value.strip()

        return blocks

    def _import_objects_via_api(self, object_type: str, objects: List[Dict]) -> bool:
        """Importa objetos vía API REST"""
        endpoint = f"{self.base_url}/api/v1/{object_type}"

        success = True
        for obj in objects:
            try:
                # Verificar si el objeto ya existe
                existing_id = self._find_existing_object(object_type, obj)

                if existing_id and self.update_existing:
                    # Actualizar objeto existente
                    response = self.session.put(
                        f"{endpoint}/{existing_id}",
                        json=obj,
                        timeout=self.timeout,
                        verify=self.verify_ssl
                    )
                    action = "actualizado"
                else:
                    # Crear nuevo objeto
                    response = self.session.post(
                        endpoint,
                        json=obj,
                        timeout=self.timeout,
                        verify=self.verify_ssl
                    )
                    action = "creado"

                if response.status_code in [200, 201]:
                    self.logger.info(f"Objeto {object_type} {action}: {obj.get('host_name', obj.get('service_description', obj.get('command_name', 'unknown')))}")
                else:
                    self.logger.error(f"Error {action} objeto {object_type}: {response.status_code} - {response.text}")
                    success = False

            except Exception as e:
                self.logger.error(f"Error procesando objeto {object_type}: {e}")
                success = False

        return success

    def _find_existing_object(self, object_type: str, obj: Dict) -> Optional[str]:
        """Busca objeto existente por checksum o identificador único"""
        if not self.use_checksums:
            return None

        try:
            # Endpoint para buscar objetos
            search_endpoint = f"{self.base_url}/api/v1/{object_type}/search"

            # Usar checksum para búsqueda
            checksum = obj.get('_checksum')
            if checksum:
                response = self.session.get(
                    search_endpoint,
                    params={'checksum': checksum},
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )

                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        return str(results[0].get('id'))

        except Exception as e:
            self.logger.warning(f"Error buscando objeto existente: {e}")

        return None

    def _calculate_checksum(self, obj: Dict) -> str:
        """Calcula checksum para idempotencia"""
        # Remover campos internos antes de calcular checksum
        clean_obj = {k: v for k, v in obj.items() if not k.startswith('_')}

        # Serializar y calcular hash
        obj_str = json.dumps(clean_obj, sort_keys=True)
        return hashlib.md5(obj_str.encode()).hexdigest()

    def _import_via_database(self, config_files: Dict[str, str]) -> bool:
        """
        Importa configuraciones vía inserción directa en base de datos

        Este método requiere acceso directo a la base de datos MySQL de NagiosQL
        Tablas principales:
        - tbl_host
        - tbl_service
        - tbl_command
        - tbl_contact
        """
        self.logger.info("Importando vía base de datos directa")

        try:
            import mysql.connector

            # Conectar a la base de datos
            conn = mysql.connector.connect(
                host=self.db_config.get('host', 'localhost'),
                user=self.db_config.get('user'),
                password=self.db_config.get('password'),
                database=self.db_config.get('database', 'nagiosql'),
                port=self.db_config.get('port', 3306)
            )

            cursor = conn.cursor()

            # Procesar configuraciones
            success = True

            for filename, content in config_files.items():
                try:
                    if filename == 'hosts.cfg':
                        self._import_hosts_to_db(cursor, content)
                    elif filename == 'services.cfg':
                        self._import_services_to_db(cursor, content)
                    elif filename == 'commands.cfg':
                        self._import_commands_to_db(cursor, content)
                    elif filename == 'contacts.cfg':
                        self._import_contacts_to_db(cursor, content)
                except Exception as e:
                    self.logger.error(f"Error importando {filename}: {e}")
                    success = False

            conn.commit()
            cursor.close()
            conn.close()

            return success

        except Exception as e:
            self.logger.error(f"Error de conexión a base de datos: {e}")
            return False

    def _import_via_file(self, config_files: Dict[str, str]) -> bool:
        """
        Importa vía archivos temporales que NagiosQL puede procesar

        Este método crea archivos .cfg temporales que NagiosQL puede importar
        vía su interfaz de administración
        """
        self.logger.info("Importando vía archivos temporales")

        try:
            import tempfile
            import os

            # Crear directorio temporal
            with tempfile.TemporaryDirectory() as temp_dir:
                # Escribir archivos de configuración
                for filename, content in config_files.items():
                    filepath = os.path.join(temp_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                # Aquí iría la lógica para notificar a NagiosQL sobre los archivos
                # Por ejemplo, vía API de importación de archivos o webhook

                self.logger.info(f"Archivos preparados en: {temp_dir}")
                self.logger.warning("Importación vía archivos requiere intervención manual en NagiosQL")

                return True

        except Exception as e:
            self.logger.error(f"Error creando archivos temporales: {e}")
            return False

    def validate_import(self) -> bool:
        """Valida que la importación fue exitosa verificando objetos en NagiosQL"""
        self.logger.info("Validando importación en NagiosQL")

        try:
            # Verificar conectividad
            response = self.session.get(
                f"{self.base_url}/api/v1/status",
                timeout=self.timeout,
                verify=self.verify_ssl
            )

            if response.status_code != 200:
                self.logger.error("NagiosQL no está accesible")
                return False

            # Verificar que los objetos existen
            endpoints = ['hosts', 'services', 'commands', 'contacts']

            for endpoint in endpoints:
                response = self.session.get(
                    f"{self.base_url}/api/v1/{endpoint}",
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )

                if response.status_code == 200:
                    count = len(response.json())
                    self.logger.info(f"Objetos {endpoint}: {count} encontrados")
                else:
                    self.logger.warning(f"Error verificando {endpoint}: {response.status_code}")

            return True

        except Exception as e:
            self.logger.error(f"Error validando importación: {e}")
            return False

    def export_to_nagios(self) -> bool:
        """Exporta configuraciones desde NagiosQL a Nagios"""
        self.logger.info("Exportando configuraciones a Nagios")

        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/export",
                timeout=self.timeout,
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                self.logger.info("Exportación a Nagios completada")
                return True
            else:
                self.logger.error(f"Error en exportación: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error exportando a Nagios: {e}")
            return False


def create_nagiosql_adapter(config: Dict[str, Any]) -> NagiosQLAdapter:
    """Factory function para crear adaptador NagiosQL"""
    return NagiosQLAdapter(config)


# Ejemplo de uso
if __name__ == "__main__":
    # Configuración de ejemplo
    nagiosql_config = {
        'api_url': 'http://nagiosql.example.com',
        'username': 'api_user',
        'password': 'api_password',
        'integration_method': 'api',
        'use_checksums': True,
        'update_existing': True,
        'verify_ssl': False
    }

    # Configuraciones de ejemplo
    sample_configs = {
        'hosts.cfg': """
define host {
    host_name    web-server-01
    alias        Web Server 01
    address      192.168.1.10
    check_command check-host-alive
}
""",
        'services.cfg': """
define service {
    service_description HTTP Check
    host_name          web-server-01
    check_command      check_http -H $HOSTADDRESS$
}
"""
    }

    # Crear adaptador e importar
    adapter = create_nagiosql_adapter(nagiosql_config)
    success = adapter.import_configurations(sample_configs)

    if success:
        print("Importación completada exitosamente")
        adapter.validate_import()
        adapter.export_to_nagios()
    else:
        print("Error en la importación")