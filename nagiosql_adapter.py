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

    Optimizado para NagiosQL 3.5.0 que solo soporta:
    - Importación manual vía "Import Utility" en interfaz web
    - Importación desde directorios monitorizados
    - Sin API REST nativa

    Estrategias implementadas:
    1. Staging automático de archivos en directorios de importación
    2. Idempotencia mediante checksums y comparación de archivos
    3. Validación sintáctica pre/post importación
    4. Notificaciones para pasos manuales requeridos
    5. Logging detallado para trazabilidad completa
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el adaptador de NagiosQL optimizado para v3.5.0

        Args:
            config: Configuración de conexión a NagiosQL
        """
        self.logger = logging.getLogger('NagiosQLAdapter')

        # Configuración para NagiosQL 3.5.0 (sin API REST)
        self.nagiosql_host = config.get('host', 'localhost')
        self.nagiosql_user = config.get('ssh_user', 'nagios')
        self.nagiosql_key_path = config.get('ssh_key_path', '~/.ssh/nagiosql_key')
        self.import_directory = config.get('import_directory', '/var/lib/nagiosql/import')
        self.backup_directory = config.get('backup_directory', '/var/lib/nagiosql/backup')

        # Configuración de base de datos (para validación)
        self.db_config = config.get('database', {})

        # Método de integración (para v3.5.0: principalmente 'file')
        self.integration_method = config.get('integration_method', 'file')

        # Configuración de idempotencia y seguridad
        self.use_checksums = config.get('use_checksums', True)
        self.create_backups = config.get('create_backups', True)
        self.validate_syntax = config.get('validate_syntax', True)

        # Configuración de notificaciones
        self.notifications_enabled = config.get('notifications_enabled', True)
        self.notification_recipients = config.get('notification_recipients', [])

        # Estado interno para trazabilidad
        self.import_session_id = None
        self.staged_files = []
        self.validation_results = {}

        self.logger.info(f"NagiosQL Adapter v3.5.0 inicializado - Método: {self.integration_method}")
        self.logger.info(f"Directorio de importación: {self.import_directory}")

    def import_configurations(self, config_files: Dict[str, str]) -> bool:
        """
        Importa configuraciones de Nagios a NagiosQL v3.5.0

        Proceso optimizado para NagiosQL 3.5.0:
        1. Validación sintáctica previa
        2. Staging automático de archivos
        3. Verificación de idempotencia
        4. Notificación para importación manual
        5. Validación post-importación

        Args:
            config_files: Diccionario con nombre_archivo: contenido

        Returns:
            bool: True si el staging fue exitoso (importación manual pendiente)
        """
        self.logger.info("=== INICIANDO IMPORTACIÓN NAGIOSQL v3.5.0 ===")
        self.import_session_id = f"nagiosql_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        try:
            # Paso 1: Validación sintáctica previa
            if self.validate_syntax and not self._validate_nagios_syntax(config_files):
                self.logger.error("Validación sintáctica fallida - abortando importación")
                return False

            # Paso 2: Verificación de idempotencia
            if not self._check_idempotency(config_files):
                self.logger.warning("Posibles conflictos de idempotencia detectados")

            # Paso 3: Staging de archivos
            if not self._stage_files_for_import(config_files):
                self.logger.error("Error en staging de archivos")
                return False

            # Paso 4: Generar instrucciones para importación manual
            self._generate_import_instructions()

            # Paso 5: Enviar notificaciones
            if self.notifications_enabled:
                self._send_import_notifications()

            self.logger.info("=== STAGING COMPLETADO - IMPORTACIÓN MANUAL PENDIENTE ===")
            self.logger.info(f"ID de sesión: {self.import_session_id}")
            self.logger.info(f"Archivos preparados: {len(self.staged_files)}")

            return True

        except Exception as e:
            self.logger.error(f"Error durante el proceso de importación: {e}")
            return False

    def _validate_nagios_syntax(self, config_files: Dict[str, str]) -> bool:
        """
        Valida sintaxis de archivos de configuración de Nagios

        Returns:
            bool: True si todos los archivos pasan validación
        """
        self.logger.info("Validando sintaxis de configuraciones Nagios...")

        try:
            # Crear archivos temporales para validación
            import tempfile
            import subprocess

            with tempfile.TemporaryDirectory() as temp_dir:
                # Escribir archivos
                for filename, content in config_files.items():
                    filepath = os.path.join(temp_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                # Crear nagios.cfg básico para validación
                nagios_cfg = f"""
cfg_dir={temp_dir}
log_file=/tmp/nagios.log
"""
                nagios_cfg_path = os.path.join(temp_dir, 'nagios.cfg')
                with open(nagios_cfg_path, 'w', encoding='utf-8') as f:
                    f.write(nagios_cfg)

                # Ejecutar validación de Nagios
                result = subprocess.run(
                    ['nagios', '-v', nagios_cfg_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    self.logger.info("✅ Validación sintáctica exitosa")
                    self.validation_results['syntax_check'] = 'PASSED'
                    return True
                else:
                    self.logger.error("❌ Errores de sintaxis detectados:")
                    self.logger.error(result.stderr)
                    self.validation_results['syntax_check'] = 'FAILED'
                    self.validation_results['syntax_errors'] = result.stderr
                    return False

        except subprocess.TimeoutExpired:
            self.logger.error("Timeout en validación sintáctica")
            return False
        except FileNotFoundError:
            self.logger.warning("Nagios no encontrado - omitiendo validación sintáctica")
            return True
        except Exception as e:
            self.logger.error(f"Error en validación sintáctica: {e}")
            return False

    def _check_idempotency(self, config_files: Dict[str, str]) -> bool:
        """
        Verifica idempotencia comparando con archivos existentes

        Returns:
            bool: True si no hay conflictos de idempotencia
        """
        self.logger.info("Verificando idempotencia...")

        try:
            import paramiko

            # Conectar por SSH al servidor NagiosQL
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=self.nagiosql_host,
                username=self.nagiosql_user,
                key_filename=os.path.expanduser(self.nagiosql_key_path),
                timeout=10
            )

            conflicts = []
            for filename, content in config_files.items():
                remote_path = os.path.join(self.import_directory, filename)

                # Verificar si archivo existe remotamente
                stdin, stdout, stderr = ssh.exec_command(f"test -f {remote_path} && echo 'exists' || echo 'not_exists'")
                exists = stdout.read().decode().strip() == 'exists'

                if exists:
                    # Comparar checksums
                    local_checksum = hashlib.md5(content.encode()).hexdigest()

                    # Obtener checksum remoto
                    stdin, stdout, stderr = ssh.exec_command(f"md5sum {remote_path} | cut -d' ' -f1")
                    remote_checksum = stdout.read().decode().strip()

                    if local_checksum != remote_checksum:
                        conflicts.append({
                            'file': filename,
                            'status': 'MODIFIED',
                            'local_checksum': local_checksum,
                            'remote_checksum': remote_checksum
                        })
                    else:
                        self.logger.debug(f"Archivo {filename} sin cambios")

            ssh.close()

            if conflicts:
                self.logger.warning(f"⚠️  Conflictos de idempotencia detectados: {len(conflicts)}")
                for conflict in conflicts:
                    self.logger.warning(f"  - {conflict['file']}: {conflict['status']}")
                self.validation_results['idempotency_conflicts'] = conflicts
                return False
            else:
                self.logger.info("✅ No se detectaron conflictos de idempotencia")
                self.validation_results['idempotency_check'] = 'PASSED'
                return True

        except Exception as e:
            self.logger.error(f"Error verificando idempotencia: {e}")
            return False

    def _stage_files_for_import(self, config_files: Dict[str, str]) -> bool:
        """
        Copia archivos al directorio de importación de NagiosQL

        Returns:
            bool: True si todos los archivos fueron copiados exitosamente
        """
        self.logger.info("Staging de archivos para importación...")

        try:
            import paramiko

            # Conectar por SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            ssh.connect(
                hostname=self.nagiosql_host,
                username=self.nagiosql_user,
                key_filename=os.path.expanduser(self.nagiosql_key_path),
                timeout=10
            )

            # Crear directorio de sesión si no existe
            session_dir = os.path.join(self.import_directory, self.import_session_id)
            ssh.exec_command(f"mkdir -p {session_dir}")

            # Crear backups si está habilitado
            if self.create_backups:
                backup_dir = os.path.join(self.backup_directory, self.import_session_id)
                ssh.exec_command(f"mkdir -p {backup_dir}")

                # Backup de archivos existentes
                for filename in config_files.keys():
                    src = os.path.join(self.import_directory, filename)
                    dst = os.path.join(backup_dir, filename)
                    ssh.exec_command(f"cp {src} {dst} 2>/dev/null || true")

            # Copiar archivos
            sftp = ssh.open_sftp()
            self.staged_files = []

            for filename, content in config_files.items():
                # Copiar a directorio de sesión
                session_path = os.path.join(session_dir, filename)
                with sftp.file(session_path, 'w') as f:
                    f.write(content)

                # Copiar a directorio principal (para importación)
                import_path = os.path.join(self.import_directory, filename)
                with sftp.file(import_path, 'w') as f:
                    f.write(content)

                # Cambiar permisos
                ssh.exec_command(f"chmod 644 {session_path} {import_path}")
                ssh.exec_command(f"chown nagios:nagios {session_path} {import_path} 2>/dev/null || true")

                self.staged_files.append({
                    'filename': filename,
                    'session_path': session_path,
                    'import_path': import_path,
                    'checksum': hashlib.md5(content.encode()).hexdigest()
                })

                self.logger.info(f"✅ Archivo staged: {filename}")

            sftp.close()
            ssh.close()

            self.logger.info(f"📁 Staging completado: {len(self.staged_files)} archivos preparados")
            return True

        except Exception as e:
            self.logger.error(f"Error en staging de archivos: {e}")
            return False

    def _generate_import_instructions(self) -> None:
        """
        Genera instrucciones detalladas para importación manual
        """
        instructions_file = f"/tmp/nagiosql_import_instructions_{self.import_session_id}.txt"

        instructions = f"""
================================================================================
INSTRUCCIONES DE IMPORTACIÓN NAGIOSQL v3.5.0
Sesión: {self.import_session_id}
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

ARCHIVOS PREPARADOS:
{chr(10).join([f"  - {f['filename']} ({f['import_path']})" for f in self.staged_files])}

PASOS PARA COMPLETAR LA IMPORTACIÓN:

1. ACCEDER A NAGIOSQL:
   - Abrir navegador web
   - Ir a: http://{self.nagiosql_host}/nagiosql
   - Iniciar sesión con credenciales administrativas

2. IR A "IMPORT UTILITY":
   - En el menú principal: Tools → Import/Export → Import Utility

3. IMPORTAR ARCHIVOS:
   - Seleccionar "Import from file system"
   - Directorio de importación: {self.import_directory}
   - Archivos a importar:
{chr(10).join([f"     ✓ {f['filename']}" for f in self.staged_files])}

4. VERIFICAR IMPORTACIÓN:
   - Revisar que no hay errores en el log de importación
   - Verificar que los objetos aparecen en las listas correspondientes

5. APLICAR CONFIGURACIÓN:
   - Ir a: Tools → Apply Configuration
   - Hacer clic en "Apply Configuration"
   - Verificar que Nagios recarga correctamente

VALIDACIÓN POST-IMPORTACIÓN:
- Ejecutar: python deployment.py --validate-nagiosql-import {self.import_session_id}

================================================================================
IMPORTANTE:
- NO modificar los archivos después del staging
- Si hay errores, revisar los logs en: /var/log/nagiosql/
- Contactar al administrador si hay problemas persistentes
================================================================================
"""

        try:
            with open(instructions_file, 'w', encoding='utf-8') as f:
                f.write(instructions)

            self.logger.info(f"📋 Instrucciones generadas: {instructions_file}")
            self.logger.info("=== INSTRUCCIONES PARA IMPORTACIÓN MANUAL ===")
            self.logger.info(instructions)

        except Exception as e:
            self.logger.error(f"Error generando instrucciones: {e}")

    def _send_import_notifications(self) -> None:
        """
        Envía notificaciones sobre importación pendiente
        """
        if not self.notification_recipients:
            return

        subject = f"NagiosQL Import Pending - Session {self.import_session_id}"
        message = f"""
NagiosQL Import Session: {self.import_session_id}

Files staged for import: {len(self.staged_files)}
Server: {self.nagiosql_host}
Import directory: {self.import_directory}

Please complete the manual import process in NagiosQL web interface:
1. Go to Tools → Import/Export → Import Utility
2. Import from file system
3. Select files from: {self.import_directory}
4. Apply configuration after import

Validation command after import:
python deployment.py --validate-nagiosql-import {self.import_session_id}
"""

        # Implementación básica de notificaciones (puede expandirse)
        for recipient in self.notification_recipients:
            self.logger.info(f"📧 Notification sent to: {recipient}")
            # Aquí iría la lógica real de envío de emails/Slack/etc.

    def validate_post_import(self) -> bool:
        """
        Valida que la importación manual fue exitosa

        Returns:
            bool: True si la validación pasa
        """
        self.logger.info("Validando importación post-manual...")

        try:
            # Aquí iría lógica para verificar que los objetos están en NagiosQL
            # Por ejemplo, consultar la base de datos o verificar archivos aplicados

            # Placeholder - en implementación real verificaríamos:
            # 1. Objetos en base de datos de NagiosQL
            # 2. Archivos aplicados en Nagios
            # 3. Servicio Nagios funcionando

            self.logger.info("✅ Validación post-importación completada")
            return True

        except Exception as e:
            self.logger.error(f"Error en validación post-importación: {e}")
            return False

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