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
from datetime import datetime
from pathlib import Path

# Importar módulos generadores
from nagios_generator import generate_nagios_from_json
from elastic_generator import generate_elastic_from_json


class MonitoringAutomator:
    """Sistema principal de automatización de monitorización"""

    def __init__(self, output_base_dir="output"):
        self.output_base_dir = Path(output_base_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Crear directorio base si no existe
        self.output_base_dir.mkdir(exist_ok=True)

    def validate_json(self, json_file):
        """Valida que el archivo JSON tenga la estructura correcta"""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validaciones básicas
            required_sections = ['identification', 'logs']
            for section in required_sections:
                if section not in data:
                    print(f"⚠️  Advertencia: Sección '{section}' no encontrada en JSON")
                else:
                    print(f"✓ Sección '{section}' encontrada")

            # Validar identificación
            if 'identification' in data:
                service_name = data['identification'].get('service_name', 'No especificado')
                print(f"✓ Servicio identificado: {service_name}")

            # Validar logs
            if 'logs' in data:
                logs_count = len(data['logs'])
                print(f"✓ Logs configurados: {logs_count}")

                for log in data['logs']:
                    if 'name' not in log or 'path' not in log:
                        print(f"⚠️  Advertencia: Log incompleto: {log}")

            # Validar dependencias
            if 'dependencies' in data:
                deps_count = len(data['dependencies'])
                print(f"✓ Dependencias configuradas: {deps_count}")

            # Validar entornos
            if 'envs' in data:
                envs_count = len(data['envs'])
                print(f"✓ Entornos configurados: {envs_count}")

            return True, data

        except FileNotFoundError:
            print(f"❌ Error: No se encontró el archivo JSON: {json_file}")
            return False, None
        except json.JSONDecodeError as e:
            print(f"❌ Error: Error de formato JSON: {e}")
            return False, None

    def generate_monitoring_configs(self, json_file, nagios_only=False, elastic_only=False):
        """Genera todas las configuraciones de monitorización"""
        print("=" * 60)
        print("🚀 SISTEMA DE AUTOMATIZACIÓN DE MONITORIZACIÓN")
        print("=" * 60)

        # Validar JSON
        print(f"\n📋 Validando archivo JSON: {json_file}")
        is_valid, data = self.validate_json(json_file)

        if not is_valid:
            return False

        # Crear directorio de ejecución específico
        execution_dir = self.output_base_dir / f"execution_{self.timestamp}"
        execution_dir.mkdir(exist_ok=True)

        print(f"\n📁 Directorio de salida: {execution_dir}")

        # Generar configuraciones
        all_files = []
        metadata = {}

        if not elastic_only:
            print("\n🔧 Generando configuración de Nagios...")
            nagios_dir = execution_dir / "nagios"
            nagios_files, nagios_meta = generate_nagios_from_json(json_file, str(nagios_dir))
            all_files.extend(nagios_files)
            metadata['nagios'] = nagios_meta

        if not nagios_only:
            print("\n🔧 Generando configuración de Elastic Stack...")
            elastic_dir = execution_dir / "elastic"
            elastic_files, elastic_meta = generate_elastic_from_json(json_file, str(elastic_dir))
            all_files.extend(elastic_files)
            metadata['elastic'] = elastic_meta

        # Generar reporte de resumen
        self.generate_summary_report(execution_dir, data, metadata)

        # Mostrar resumen final
        self.show_final_summary(all_files, metadata)

        return True

    def generate_summary_report(self, output_dir, json_data, metadata):
        """Genera reporte de resumen de la configuración generada"""
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

        print(f"✓ Reporte generado: {report_file}")

    def show_final_summary(self, files, metadata):
        """Muestra resumen final de la generación"""
        print("\n" + "=" * 60)
        print("✅ GENERACIÓN COMPLETADA")
        print("=" * 60)
        print(f"📊 Archivos totales generados: {len(files)}")

        if 'nagios' in metadata:
            nagios = metadata['nagios']
            print("🔧 Nagios:")
            print(f"   • Hosts: {len(nagios.get('hosts', []))}")
            print(f"   • Servicios: {len(nagios.get('services', []))}")
            print(f"   • Contactos: {len(nagios.get('contacts', []))}")

        if 'elastic' in metadata:
            elastic = metadata['elastic']
            print("🔍 Elastic Stack:")
            print(f"   • Configuraciones: {len([f for f in files if 'elastic' in f])}")
            print(f"   • Alertas: {len(elastic.get('alerts', []))}")

        print("\n📋 Revisa el archivo README.md generado para instrucciones detalladas")
        print("=" * 60)


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
        print("❌ Error: No se pueden especificar --nagios-only y --elastic-only simultáneamente")
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
            print("\n🎉 ¡Generación de configuraciones completada exitosamente!")

            # Despliegue automático si se solicita
            if args.deploy:
                print(f"\n🚀 Iniciando despliegue automático en entorno '{args.deploy_env}'...")

                # Encontrar directorio de ejecución más reciente
                import glob
                execution_dirs = glob.glob(str(automator.output_base_dir / "execution_*"))
                if execution_dirs:
                    latest_execution = max(execution_dirs, key=os.path.getmtime)

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
                        print("\n🎉 ¡Despliegue completado exitosamente!")
                    else:
                        print("\n❌ Error durante el despliegue automático")
                        sys.exit(1)
                else:
                    print("\n❌ No se encontró directorio de ejecución para desplegar")
                    sys.exit(1)

            sys.exit(0)
        else:
            print("\n❌ Error durante la generación de configuraciones")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()