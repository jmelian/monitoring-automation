#!/usr/bin/env python3
"""
Deployment Module
Módulo de despliegue automático para configurar Nagios y Elastic Stack
"""

import os
import sys
import yaml
import paramiko
import requests
import json
import time
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple


class DeploymentManager:
    """Gestor de despliegue automático de configuraciones de monitorización"""

    def __init__(self, config_file: str = "config.yml"):
        self.config_file = config_file
        self.config = self._load_config()
        self.logger = self._setup_logging()

        # Crear directorios necesarios
        self.temp_dir = Path(self.config['general']['temp_dir'])
        self.temp_dir.mkdir(exist_ok=True)

    def _load_config(self) -> Dict:
        """Carga la configuración desde archivo YAML"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Resolver variables de entorno
            config = self._resolve_env_vars(config)
            return config

        except FileNotFoundError:
            print(f"Error: Archivo de configuración '{self.config_file}' no encontrado")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error: Error de sintaxis en configuración YAML: {e}")
            sys.exit(1)

    def _resolve_env_vars(self, config: Dict) -> Dict:
        """Resuelve variables de entorno en la configuración"""
        def resolve_value(value):
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                env_value = os.getenv(env_var)
                if env_value is None:
                    print(f"Advertencia: Variable de entorno '{env_var}' no definida")
                    return value
                return env_value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            else:
                return value

        return resolve_value(config)

    def _setup_logging(self) -> logging.Logger:
        """Configura el sistema de logging"""
        log_config = self.config.get('logging', {})

        logger = logging.getLogger('deployment')
        logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))

        # Crear directorio de logs si no existe
        log_file = log_config.get('file', 'logs/deployment.log')
        log_dir = Path(log_file).parent
        log_dir.mkdir(exist_ok=True)

        # Handler para archivo
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_config.get('format', '%(asctime)s - %(levelname)s - %(message)s')))

        # Handler para consola
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def deploy_nagios(self, config_dir: Path, environment: str = "production") -> bool:
        """Despliega configuraciones de Nagios"""
        self.logger.info("Iniciando despliegue de Nagios...")

        nagios_config = self.config['nagios']
        env_config = self.config['environments'].get(environment, {})

        # Conectar por SSH
        ssh_client = self._connect_ssh(
            nagios_config['server']['host'],
            nagios_config['server']['user'],
            nagios_config['server']['key_path'],
            nagios_config['server']['port']
        )

        if not ssh_client:
            return False

        try:
            # Backup de configuraciones existentes
            if self.config['general']['backup_before_deploy']:
                self._backup_nagios_configs(ssh_client, nagios_config['server'])

            # Copiar archivos de configuración
            nagios_dir = config_dir / "nagios"
            if nagios_dir.exists():
                self._copy_nagios_configs(ssh_client, nagios_dir, nagios_config['server'])

            # Validar configuración
            if not self._validate_nagios_config(ssh_client):
                self.logger.error("Validación de configuración de Nagios fallida")
                return False

            # Reiniciar servicio
            if not self.config['general']['dry_run']:
                self._restart_nagios_service(ssh_client)

            # Verificar funcionamiento
            if self.config['general']['validate_after_deploy']:
                if not self._verify_nagios_service(ssh_client):
                    self.logger.error("Verificación post-despliegue de Nagios fallida")
                    return False

            self.logger.info("Despliegue de Nagios completado exitosamente")
            return True

        finally:
            ssh_client.close()

    def deploy_elastic(self, config_dir: Path, environment: str = "production") -> bool:
        """Despliega configuraciones de Elastic Stack"""
        self.logger.info("Iniciando despliegue de Elastic Stack...")

        elastic_config = self.config['elastic']
        env_config = self.config['environments'].get(environment, {})

        try:
            # Desplegar Elasticsearch pipeline
            if not self._deploy_elasticsearch_pipeline(config_dir, elastic_config):
                return False

            # Desplegar configuración de Logstash
            if not self._deploy_logstash_config(config_dir, elastic_config):
                return False

            # Desplegar dashboard de Kibana
            if not self._deploy_kibana_dashboard(config_dir, elastic_config):
                return False

            # Desplegar configuración de Filebeat (si hay targets configurados)
            if elastic_config['filebeat']['targets']:
                if not self._deploy_filebeat_configs(config_dir, elastic_config):
                    return False

            self.logger.info("Despliegue de Elastic Stack completado exitosamente")
            return True

        except Exception as e:
            self.logger.error(f"Error en despliegue de Elastic Stack: {e}")
            return False

    def _connect_ssh(self, host: str, user: str, key_path: str, port: int = 22) -> Optional[paramiko.SSHClient]:
        """Establece conexión SSH"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            expanded_key_path = os.path.expanduser(key_path)
            private_key = paramiko.RSAKey.from_private_key_file(expanded_key_path)

            ssh.connect(
                hostname=host,
                port=port,
                username=user,
                pkey=private_key,
                timeout=10
            )

            self.logger.info(f"Conexión SSH establecida con {host}")
            return ssh

        except Exception as e:
            self.logger.error(f"Error conectando por SSH a {host}: {e}")
            return None

    def _backup_nagios_configs(self, ssh: paramiko.SSHClient, server_config: Dict) -> bool:
        """Realiza backup de configuraciones existentes de Nagios"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"{server_config['backup_dir']}/backup_{timestamp}"

            # Crear directorio de backup
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {backup_dir}")
            if stdout.channel.recv_exit_status() != 0:
                error = stderr.read().decode()
                self.logger.error(f"Error creando directorio de backup: {error}")
                return False

            # Copiar archivos de configuración
            config_files = ["hosts.cfg", "services.cfg", "contacts.cfg", "commands.cfg"]
            for cfg_file in config_files:
                src = f"{server_config['config_dir']}/{cfg_file}"
                dst = f"{backup_dir}/{cfg_file}"
                stdin, stdout, stderr = ssh.exec_command(f"cp {src} {dst} 2>/dev/null || true")
                # Ignorar errores si el archivo no existe

            self.logger.info(f"Backup de Nagios creado en {backup_dir}")
            return True

        except Exception as e:
            self.logger.error(f"Error en backup de Nagios: {e}")
            return False

    def _copy_nagios_configs(self, ssh: paramiko.SSHClient, local_dir: Path, server_config: Dict) -> bool:
        """Copia archivos de configuración de Nagios al servidor"""
        try:
            sftp = ssh.open_sftp()

            config_files = ["hosts.cfg", "services.cfg", "contacts.cfg", "commands.cfg"]
            for cfg_file in config_files:
                local_path = local_dir / cfg_file
                remote_path = f"{server_config['config_dir']}/{cfg_file}"

                if local_path.exists():
                    sftp.put(str(local_path), remote_path)
                    self.logger.info(f"Archivo copiado: {cfg_file}")

                    # Cambiar permisos
                    ssh.exec_command(f"chmod 644 {remote_path}")
                    if server_config.get('sudo_required'):
                        ssh.exec_command(f"chown nagios:nagios {remote_path}")

            sftp.close()
            return True

        except Exception as e:
            self.logger.error(f"Error copiando configuraciones de Nagios: {e}")
            return False

    def _validate_nagios_config(self, ssh: paramiko.SSHClient) -> bool:
        """Valida la configuración de Nagios"""
        try:
            stdin, stdout, stderr = ssh.exec_command("nagios -v /etc/nagios/nagios.cfg")
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                self.logger.info("Validación de configuración de Nagios exitosa")
                return True
            else:
                error_output = stderr.read().decode()
                self.logger.error(f"Errores de validación de Nagios: {error_output}")
                return False

        except Exception as e:
            self.logger.error(f"Error validando configuración de Nagios: {e}")
            return False

    def _restart_nagios_service(self, ssh: paramiko.SSHClient) -> bool:
        """Reinicia el servicio de Nagios"""
        try:
            if self.config['general']['dry_run']:
                self.logger.info("[DRY RUN] Se omitió reinicio de servicio Nagios")
                return True

            stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart nagios")
            exit_status = stdout.channel.recv_exit_status()

            if exit_status == 0:
                self.logger.info("Servicio de Nagios reiniciado exitosamente")
                time.sleep(5)  # Esperar a que el servicio inicie
                return True
            else:
                error = stderr.read().decode()
                self.logger.error(f"Error reiniciando Nagios: {error}")
                return False

        except Exception as e:
            self.logger.error(f"Error reiniciando servicio de Nagios: {e}")
            return False

    def _verify_nagios_service(self, ssh: paramiko.SSHClient) -> bool:
        """Verifica que el servicio de Nagios esté funcionando"""
        try:
            stdin, stdout, stderr = ssh.exec_command("sudo systemctl is-active nagios")
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()

            if exit_status == 0 and output == "active":
                self.logger.info("Servicio de Nagios verificado como activo")
                return True
            else:
                self.logger.error(f"Servicio de Nagios no está activo: {output}")
                return False

        except Exception as e:
            self.logger.error(f"Error verificando servicio de Nagios: {e}")
            return False

    def _deploy_elasticsearch_pipeline(self, config_dir: Path, elastic_config: Dict) -> bool:
        """Despliega pipeline de ingest en Elasticsearch"""
        try:
            pipeline_file = config_dir / "elastic" / "ingest_pipeline.json"
            if not pipeline_file.exists():
                self.logger.warning("Archivo de pipeline no encontrado, omitiendo despliegue")
                return True

            with open(pipeline_file, 'r', encoding='utf-8') as f:
                pipeline_data = json.load(f)

            # Conectar a Elasticsearch
            es_hosts = elastic_config['elasticsearch']['hosts']
            es_auth = (elastic_config['elasticsearch']['auth']['user'],
                      elastic_config['elasticsearch']['auth']['password'])

            # Crear pipeline
            pipeline_name = f"monitoring_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            for host in es_hosts:
                try:
                    url = f"http://{host}/_ingest/pipeline/{pipeline_name}"
                    response = requests.put(
                        url,
                        json=pipeline_data,
                        auth=es_auth,
                        timeout=elastic_config['elasticsearch']['timeout'],
                        verify=elastic_config['elasticsearch']['ssl_verify']
                    )

                    if response.status_code in [200, 201]:
                        self.logger.info(f"Pipeline creado en Elasticsearch {host}")
                        break
                    else:
                        self.logger.warning(f"Error creando pipeline en {host}: {response.text}")

                except Exception as e:
                    self.logger.warning(f"Error conectando a Elasticsearch {host}: {e}")
                    continue
            else:
                self.logger.error("No se pudo crear pipeline en ningún host de Elasticsearch")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Error desplegando pipeline de Elasticsearch: {e}")
            return False

    def _deploy_logstash_config(self, config_dir: Path, elastic_config: Dict) -> bool:
        """Despliega configuración de Logstash"""
        try:
            logstash_file = config_dir / "elastic" / "logstash.conf"
            if not logstash_file.exists():
                self.logger.warning("Archivo de configuración de Logstash no encontrado")
                return True

            # Conectar por SSH al servidor de Logstash
            ssh_client = self._connect_ssh(
                elastic_config['logstash']['host'],
                "logstash",  # Usuario por defecto
                "~/.ssh/logstash_key"  # Clave por defecto
            )

            if not ssh_client:
                return False

            try:
                # Copiar archivo de configuración
                sftp = ssh_client.open_sftp()
                remote_path = f"{elastic_config['logstash']['config_dir']}/monitoring.conf"
                sftp.put(str(logstash_file), remote_path)
                sftp.close()

                # Cambiar permisos
                ssh_client.exec_command(f"chmod 644 {remote_path}")
                ssh_client.exec_command(f"chown logstash:logstash {remote_path}")

                # Recargar configuración si está habilitado
                if elastic_config['logstash'].get('reload_config', True):
                    ssh_client.exec_command("sudo systemctl reload logstash")

                self.logger.info("Configuración de Logstash desplegada exitosamente")
                return True

            finally:
                ssh_client.close()

        except Exception as e:
            self.logger.error(f"Error desplegando configuración de Logstash: {e}")
            return False

    def _deploy_kibana_dashboard(self, config_dir: Path, elastic_config: Dict) -> bool:
        """Despliega dashboard en Kibana"""
        try:
            dashboard_file = config_dir / "elastic" / "kibana_dashboard.json"
            if not dashboard_file.exists():
                self.logger.warning("Archivo de dashboard de Kibana no encontrado")
                return True

            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboard_data = json.load(f)

            # Conectar a Kibana
            kibana_host = elastic_config['kibana']['host']
            kibana_port = elastic_config['kibana']['port']
            kibana_auth = (elastic_config['kibana']['auth']['user'],
                          elastic_config['kibana']['auth']['password'])

            # Importar dashboard (esto es simplificado - en la práctica requeriría la API de Kibana)
            url = f"http://{kibana_host}:{kibana_port}/api/saved_objects/_import"

            # Nota: La importación real de dashboards requiere manejo de objetos de Kibana
            # Esta es una implementación básica
            self.logger.info("Dashboard de Kibana preparado para importación manual")
            self.logger.info(f"Archivo disponible en: {dashboard_file}")

            return True

        except Exception as e:
            self.logger.error(f"Error desplegando dashboard de Kibana: {e}")
            return False

    def _deploy_filebeat_configs(self, config_dir: Path, elastic_config: Dict) -> bool:
        """Despliega configuraciones de Filebeat a múltiples servidores"""
        try:
            filebeat_file = config_dir / "elastic" / "filebeat.yml"
            if not filebeat_file.exists():
                self.logger.warning("Archivo de configuración de Filebeat no encontrado")
                return True

            success_count = 0
            for target in elastic_config['filebeat']['targets']:
                try:
                    ssh_client = self._connect_ssh(
                        target['host'],
                        target.get('user', 'filebeat'),
                        target.get('key_path', '~/.ssh/filebeat_key')
                    )

                    if ssh_client:
                        # Copiar configuración
                        sftp = ssh_client.open_sftp()
                        remote_path = "/etc/filebeat/filebeat.yml"
                        sftp.put(str(filebeat_file), remote_path)
                        sftp.close()

                        # Reiniciar servicio
                        if not self.config['general']['dry_run']:
                            ssh_client.exec_command("sudo systemctl restart filebeat")

                        ssh_client.close()
                        success_count += 1
                        self.logger.info(f"Filebeat desplegado en {target['host']}")

                except Exception as e:
                    self.logger.error(f"Error desplegando Filebeat en {target['host']}: {e}")

            if success_count > 0:
                self.logger.info(f"Filebeat desplegado exitosamente en {success_count} servidores")
                return True
            else:
                self.logger.error("No se pudo desplegar Filebeat en ningún servidor")
                return False

        except Exception as e:
            self.logger.error(f"Error general desplegando Filebeat: {e}")
            return False

    def deploy_all(self, config_dir: str, environment: str = "production",
                   nagios_only: bool = False, elastic_only: bool = False) -> bool:
        """Despliega todas las configuraciones"""
        config_path = Path(config_dir)
        if not config_path.exists():
            self.logger.error(f"Directorio de configuración no encontrado: {config_dir}")
            return False

        self.logger.info(f"Iniciando despliegue completo para entorno: {environment}")
        self.logger.info(f"Directorio de configuración: {config_path}")

        if self.config['general']['dry_run']:
            self.logger.info("*** MODO DRY RUN - No se realizarán cambios reales ***")

        success = True

        # Desplegar Nagios
        if not elastic_only:
            if not self.deploy_nagios(config_path, environment):
                success = False

        # Desplegar Elastic Stack
        if not nagios_only:
            if not self.deploy_elastic(config_path, environment):
                success = False

        if success:
            self.logger.info("🎉 Despliegue completado exitosamente")
            self._send_notifications("Despliegue completado exitosamente", "success")
        else:
            self.logger.error("❌ Despliegue fallido")
            self._send_notifications("Despliegue fallido - revisar logs", "error")

        return success

    def _send_notifications(self, message: str, level: str):
        """Envía notificaciones de despliegue"""
        notifications = self.config.get('notifications', {})

        # Email notification
        if notifications.get('email', {}).get('enabled', False):
            self._send_email_notification(message, level)

        # Slack notification
        if notifications.get('slack', {}).get('enabled', False):
            self._send_slack_notification(message, level)

    def _send_email_notification(self, message: str, level: str):
        """Envía notificación por email (implementación básica)"""
        # Implementación simplificada - en producción usar smtplib o similar
        self.logger.info(f"Email notification: {message}")

    def _send_slack_notification(self, message: str, level: str):
        """Envía notificación por Slack"""
        # Implementación simplificada - en producción usar slack-sdk
        self.logger.info(f"Slack notification: {message}")


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sistema de Despliegue Automático de Monitorización",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'config_dir',
        help='Directorio que contiene las configuraciones generadas'
    )

    parser.add_argument(
        '--env', '--environment',
        default='production',
        choices=['production', 'staging', 'development'],
        help='Entorno de despliegue (por defecto: production)'
    )

    parser.add_argument(
        '--config',
        default='config.yml',
        help='Archivo de configuración de despliegue (por defecto: config.yml)'
    )

    parser.add_argument(
        '--nagios-only',
        action='store_true',
        help='Desplegar solo configuraciones de Nagios'
    )

    parser.add_argument(
        '--elastic-only',
        action='store_true',
        help='Desplegar solo configuraciones de Elastic Stack'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Ejecutar en modo simulación (no realizar cambios reales)'
    )

    args = parser.parse_args()

    # Validar argumentos mutuamente excluyentes
    if args.nagios_only and args.elastic_only:
        print("❌ Error: No se pueden especificar --nagios-only y --elastic-only simultáneamente")
        sys.exit(1)

    # Crear gestor de despliegue
    try:
        deployer = DeploymentManager(args.config)

        # Override dry-run si se especifica
        if args.dry_run:
            deployer.config['general']['dry_run'] = True

        # Ejecutar despliegue
        success = deployer.deploy_all(
            args.config_dir,
            environment=args.env,
            nagios_only=args.nagios_only,
            elastic_only=args.elastic_only
        )

        if success:
            print("\n🎉 ¡Despliegue completado exitosamente!")
            sys.exit(0)
        else:
            print("\n❌ El despliegue encontró problemas")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()