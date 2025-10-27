#!/usr/bin/env python3
"""
Monitoring Automation System
Sistema principal para automatizar la configuración de monitorización
basado en formularios JSON para Nagios y Elastic Stack
"""

import json
import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Configurar logging global
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring_automator.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Importar módulos generadores
from nagios_generator import generate_nagios_from_json
from elastic_generator import generate_elastic_from_json
from plugins.service_discovery import discover_services


class MonitoringAutomator:
    """Sistema principal de automatización de monitorización"""

    def __init__(self, output_base_dir="output"):
        self.output_base_dir = Path(output_base_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger = logging.getLogger('MonitoringAutomator')

        # Crear directorio base si no existe
        self.output_base_dir.mkdir(exist_ok=True)
        self.logger.info(f"Directorio base de salida inicializado: {self.output_base_dir}")

    def validate_json(self, json_file):
        """Valida que el archivo JSON tenga la estructura correcta"""
        self.logger.info(f"Iniciando validación del archivo JSON: {json_file}")
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.debug(f"Archivo JSON cargado exitosamente: {len(data)} secciones principales")

            # Validaciones básicas
            required_sections = ['identification', 'logs']
            for section in required_sections:
                if section not in data:
                    self.logger.warning(f"Sección '{section}' no encontrada en JSON")
                else:
                    self.logger.info(f"Sección '{section}' encontrada")

            # Validar identificación
            if 'identification' in data:
                service_name = data['identification'].get('service_name', 'No especificado')
                priority = data['identification'].get('priority', 'No especificada')
                self.logger.info(f"Servicio identificado: {service_name} (Prioridad: {priority})")

            # Validar logs
            if 'logs' in data:
                logs_count = len(data['logs'])
                self.logger.info(f"Logs configurados: {logs_count}")

                for i, log in enumerate(data['logs']):
                    if 'name' not in log or 'path' not in log:
                        self.logger.warning(f"Log {i} incompleto: {log}")
                    else:
                        self.logger.debug(f"Log {i}: {log.get('name')} -> {log.get('path')}")

            # Validar dependencias
            if 'dependencies' in data:
                deps_count = len(data['dependencies'])
                self.logger.info(f"Dependencias configuradas: {deps_count}")

                # Validar que dependencias externas tengan host configurado
                for i, dep in enumerate(data['dependencies']):
                    dep_name = dep.get('name', 'N/A')
                    dep_nature = dep.get('nature', 'Interna')
                    dep_protocol = dep.get('check_protocol', 'tcp')
                    self.logger.debug(f"Dependencia {i}: {dep_name} ({dep_nature}, {dep_protocol})")

                    if dep.get('nature') == 'Externa':
                        if not dep.get('host') or dep.get('host').strip() == '':
                            self.logger.warning(f"Dependencia externa '{dep_name}' no tiene host configurado")
                        else:
                            self.logger.info(f"Dependencia externa '{dep_name}' tiene host: {dep.get('host')}")

            # Validar entornos
            if 'envs' in data:
                envs_count = len(data['envs'])
                self.logger.info(f"Entornos configurados: {envs_count}")

                for i, env in enumerate(data['envs']):
                    env_name = env.get('name', 'unknown')
                    env_desc = env.get('desc', 'Sin descripción')
                    orchestrator = env.get('orchestrator', 'none')
                    hosts_count = len(env.get('hosts', []))
                    self.logger.debug(f"Entorno {i}: {env_name} ({env_desc}) - {orchestrator} - {hosts_count} hosts")

            # Validar health API
            if data.get('health_api'):
                health_details = data.get('health_api_details', {})
                endpoint = health_details.get('endpoint', 'No especificado')
                interval = health_details.get('interval_sec', 'No especificado')
                self.logger.info(f"Health API configurado: {endpoint} (intervalo: {interval}s)")

            # Validar responsables
            if 'responsables' in data:
                resp_count = len(data['responsables'])
                self.logger.info(f"Responsables configurados: {resp_count}")
                for resp in data['responsables']:
                    self.logger.debug(f"Responsable: {resp.get('nombre')} <{resp.get('email')}>")

            self.logger.info("Validación del JSON completada exitosamente")
            return True, data

        except FileNotFoundError:
            self.logger.error(f"No se encontró el archivo JSON: {json_file}")
            return False, None
        except json.JSONDecodeError as e:
            self.logger.error(f"Error de formato JSON: {e}")
            return False, None
        except Exception as e:
            self.logger.error(f"Error inesperado durante validación: {e}")
            return False, None

    def generate_monitoring_configs(self, json_file, nagios_only=False, elastic_only=False):
        """Genera todas las configuraciones de monitorización"""
        self.logger.info("=" * 60)
        self.logger.info("SISTEMA DE AUTOMATIZACION DE MONITORIZACION")
        self.logger.info("=" * 60)

        # Validar JSON
        self.logger.info(f"Validando archivo JSON: {json_file}")
        is_valid, data = self.validate_json(json_file)

        if not is_valid:
            self.logger.error("Validación del JSON fallida, abortando generación")
            return False

        # Auto-detección de servicios
        self.logger.info("Ejecutando auto-detección de servicios...")
        try:
            original_deps_count = len(data.get('dependencies', []))
            data = discover_services(data)
            new_deps_count = len(data.get('dependencies', []))
            self.logger.info(f"Auto-detección completada. Dependencias: {original_deps_count} -> {new_deps_count}")
        except Exception as e:
            self.logger.error(f"Error en auto-detección de servicios: {e}")
            return False

        # Crear directorio de ejecución específico
        execution_dir = self.output_base_dir / f"execution_{self.timestamp}"
        execution_dir.mkdir(exist_ok=True)
        self.logger.info(f"Directorio de salida creado: {execution_dir}")

        # Generar configuraciones
        all_files = []
        metadata = {}

        if not elastic_only:
            self.logger.info("Generando configuración de Nagios...")
            try:
                nagios_dir = execution_dir / "nagios"
                nagios_files, nagios_meta = generate_nagios_from_json(json_file, str(nagios_dir))
                all_files.extend(nagios_files)
                metadata['nagios'] = nagios_meta
                self.logger.info(f"Configuración de Nagios generada: {len(nagios_files)} archivos")
            except Exception as e:
                self.logger.error(f"Error generando configuración de Nagios: {e}")
                return False

        if not nagios_only:
            self.logger.info("Generando configuración de Elastic Stack...")
            try:
                elastic_dir = execution_dir / "elastic"
                elastic_files, elastic_meta = generate_elastic_from_json(json_file, str(elastic_dir))
                all_files.extend(elastic_files)
                metadata['elastic'] = elastic_meta
                self.logger.info(f"Configuración de Elastic Stack generada: {len(elastic_files)} archivos")
            except Exception as e:
                self.logger.error(f"Error generando configuración de Elastic Stack: {e}")
                return False

        # Generar reporte de resumen
        try:
            self.generate_summary_report(execution_dir, data, metadata)
            self.logger.info("Reporte de resumen generado")
        except Exception as e:
            self.logger.error(f"Error generando reporte de resumen: {e}")

        # Mostrar resumen final
        self.show_final_summary(all_files, metadata)

        self.logger.info("Generación de configuraciones completada exitosamente")
        return True

    def generate_summary_report(self, output_dir, json_data, metadata):
        """Genera reporte de resumen de la configuración generada"""
        self.logger.debug("Generando reporte de resumen...")
        report_file = output_dir / "README.md"

        service_name = json_data.get('identification', {}).get('service_name', 'Servicio desconocido')
        priority = json_data.get('identification', {}).get('priority', 'No especificada')

        report_content = f"""# Configuración de Monitorización - {service_name}

**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Servicio:** {service_name}
**Prioridad:** {priority}

## Resumen de Configuración

### Información del Servicio
- **Descripción:** {json_data.get('identification', {}).get('service_desc', 'No especificada')}
- **Tecnologías:** {', '.join([f"{tech.get('technology', '')} {tech.get('version', '')}" for tech in json_data.get('tech_stack', [])])}
- **Responsables:** {', '.join([resp.get('nombre', '') for resp in json_data.get('responsables', [])])}

### Configuración de Nagios
- **Hosts configurados:** {len(metadata.get('nagios', {}).get('hosts', []))}
- **Servicios configurados:** {len(metadata.get('nagios', {}).get('services', []))}
- **Contactos configurados:** {len(metadata.get('nagios', {}).get('contacts', []))}

### Configuración de Elastic Stack
- **Logs configurados:** {len(json_data.get('logs', []))}
- **Alertas configuradas:** {len(metadata.get('elastic', {}).get('alerts', []))}
- **Centralized logs:** {json_data.get('centralized_logs', 'No especificado')}

## Archivos Generados

### Nagios
"""

        if 'nagios' in metadata:
            nagios_dir = output_dir / "nagios"
            if nagios_dir.exists():
                report_content += f"""
- `hosts.cfg` - Definición de hosts ({len(metadata['nagios']['hosts'])} hosts)
- `services.cfg` - Definición de servicios ({len(metadata['nagios']['services'])} servicios)
- `contacts.cfg` - Grupos de contactos ({len(metadata['nagios']['contacts'])} contactos)
- `commands.cfg` - Comandos de chequeo
- `nagios.cfg` - Configuración principal
"""

        report_content += "\n### Elastic Stack\n" if 'elastic' in metadata else "\n### Elastic Stack (No generado)\n"

        if 'elastic' in metadata:
            elastic_dir = output_dir / "elastic"
            if elastic_dir.exists():
                report_content += """
- `filebeat.yml` - Configuración de Filebeat
- `logstash.conf` - Configuración de Logstash
- `ingest_pipeline.json` - Pipeline de procesamiento
- `index_template.json` - Template de índices
- `kibana_dashboard.json` - Dashboard básico
- `alerts.json` - Configuración de alertas
"""

        report_content += """

## Dependencias Configuradas

"""

        for dep in json_data.get('dependencies', []):
            report_content += f"""- **{dep.get('name', 'N/A')}**
  - Tipo: {dep.get('type', 'N/A')}
  - Impacto: {dep.get('impact', 'N/A')}
  - Puerto: {dep.get('port', 'N/A')}
  - Protocolo: {dep.get('check_protocol', 'N/A')}
  - Efecto: {dep.get('effect', 'N/A')}

"""

        report_content += """

## Logs Configurados

"""

        for log in json_data.get('logs', []):
            report_content += f"""- **{log.get('name', 'N/A')}**
  - Ruta: {log.get('path', 'N/A')}
  - Formato: {log.get('format', 'N/A')}
  - Retención: {log.get('retention_value', 'N/A')}
  - Patrones: {', '.join(log.get('patterns', []))}

"""

        # Instrucciones de despliegue
        report_content += """
## Instrucciones de Despliegue

### Nagios
1. Copiar los archivos `.cfg` a `/etc/nagios/objects/`
2. Reiniciar servicio Nagios: `systemctl restart nagios`
3. Verificar configuración: `nagios -v /etc/nagios/nagios.cfg`

### Elastic Stack
1. **Filebeat:** Copiar `filebeat.yml` a `/etc/filebeat/`
2. **Logstash:** Copiar `logstash.conf` a `/etc/logstash/conf.d/`
3. **Elasticsearch:** Crear el pipeline y template usando las APIs
4. **Kibana:** Importar el dashboard y configurar las alertas

## Notas Adicionales
- Verificar que todas las rutas de logs sean accesibles
- Ajustar permisos de archivos según sea necesario
- Probar la configuración en ambiente de desarrollo primero
"""

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        self.logger.info(f"Reporte generado: {report_file}")

    def show_final_summary(self, files, metadata):
        """Muestra resumen final de la generación"""
        self.logger.info("=" * 60)
        self.logger.info("GENERACIÓN COMPLETADA")
        self.logger.info("=" * 60)
        self.logger.info(f"Archivos totales generados: {len(files)}")

        if 'nagios' in metadata:
            nagios = metadata['nagios']
            self.logger.info("Nagios:")
            self.logger.info(f"   • Hosts: {len(nagios.get('hosts', []))}")
            self.logger.info(f"   • Servicios: {len(nagios.get('services', []))}")
            self.logger.info(f"   • Contactos: {len(nagios.get('contacts', []))}")

        if 'elastic' in metadata:
            elastic = metadata['elastic']
            self.logger.info("Elastic Stack:")
            self.logger.info(f"   • Configuraciones: {len([f for f in files if 'elastic' in f])}")
            self.logger.info(f"   • Alertas: {len(elastic.get('alerts', []))}")

        self.logger.info("Revisa el archivo README.md generado para instrucciones detalladas")
        self.logger.info("=" * 60)


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Sistema de Automatización de Monitorización",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python monitoring_automator.py servicio.json
  python monitoring_automator.py servicio.json --nagios-only
  python monitoring_automator.py servicio.json --elastic-only
  python monitoring_automator.py servicio.json -o /ruta/personalizada
        """
    )

    parser.add_argument(
        'json_file',
        help='Archivo JSON generado por el formulario de monitorización'
    )

    parser.add_argument(
        '--nagios-only',
        action='store_true',
        help='Generar solo configuración de Nagios'
    )

    parser.add_argument(
        '--elastic-only',
        action='store_true',
        help='Generar solo configuración de Elastic Stack'
    )

    parser.add_argument(
        '-o', '--output-dir',
        default='output',
        help='Directorio base de salida (por defecto: output)'
    )

    parser.add_argument(
        '--deploy',
        action='store_true',
        help='Desplegar configuraciones automáticamente después de generarlas'
    )

    parser.add_argument(
        '--deploy-env',
        default='production',
        choices=['production', 'staging', 'development'],
        help='Entorno para despliegue automático (por defecto: production)'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='Monitoring Automator v1.0'
    )

    args = parser.parse_args()

    # Validar argumentos mutuamente excluyentes
    if args.nagios_only and args.elastic_only:
        print("ERROR: No se pueden especificar --nagios-only y --elastic-only simultaneamente")
        sys.exit(1)

    # Crear automatizador y generar configuraciones
    automator = MonitoringAutomator(args.output_dir)

    try:
        success = automator.generate_monitoring_configs(
            args.json_file,
            nagios_only=args.nagios_only,
            elastic_only=args.elastic_only
        )

        if success:
            automator.logger.info("Generación de configuraciones completada exitosamente!")

            # Despliegue automático si se solicita
            if args.deploy:
                automator.logger.info(f"Iniciando despliegue automático en entorno '{args.deploy_env}'...")

                # Encontrar directorio de ejecución más reciente
                import glob
                execution_dirs = glob.glob(str(automator.output_base_dir / "execution_*"))
                if execution_dirs:
                    latest_execution = max(execution_dirs, key=os.path.getmtime)
                    automator.logger.debug(f"Directorio de ejecución encontrado: {latest_execution}")

                    # Importar y ejecutar despliegue
                    from deployment import DeploymentManager
                    deployer = DeploymentManager()

                    deploy_success = deployer.deploy_all(
                        latest_execution,
                        environment=args.deploy_env,
                        nagios_only=args.nagios_only,
                        elastic_only=args.elastic_only
                    )

                    if deploy_success:
                        automator.logger.info("Despliegue completado exitosamente!")
                    else:
                        automator.logger.error("Error durante el despliegue automático")
                        sys.exit(1)
                else:
                    automator.logger.error("No se encontró directorio de ejecución para desplegar")
                    sys.exit(1)

            sys.exit(0)
        else:
            automator.logger.error("Error durante la generación de configuraciones")
            sys.exit(1)

    except KeyboardInterrupt:
        automator.logger.warning("Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        automator.logger.error(f"Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()