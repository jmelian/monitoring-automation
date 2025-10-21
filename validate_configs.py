#!/usr/bin/env python3
"""
Config Validation System
Sistema para validar las configuraciones generadas de Nagios y Elastic Stack
"""

import os
import sys
import json
import yaml
import re
from pathlib import Path


class ConfigValidator:
    """Validador de configuraciones de monitorización"""

    def __init__(self, config_dir):
        self.config_dir = Path(config_dir)
        self.errors = []
        self.warnings = []
        self.success = []

    def add_error(self, message):
        """Agregar error de validación"""
        self.errors.append(f"❌ {message}")
        print(f"❌ {message}")

    def add_warning(self, message):
        """Agregar advertencia de validación"""
        self.warnings.append(f"⚠️  {message}")
        print(f"⚠️  {message}")

    def add_success(self, message):
        """Agregar éxito de validación"""
        self.success.append(f"✓ {message}")
        print(f"✓ {message}")

    def validate_nagios_configs(self):
        """Validar configuraciones de Nagios"""
        print("\n🔧 Validando configuración de Nagios...")

        nagios_dir = self.config_dir / "nagios"
        if not nagios_dir.exists():
            self.add_error(f"Directorio de Nagios no encontrado: {nagios_dir}")
            return False

        required_files = ["hosts.cfg", "services.cfg", "contacts.cfg", "commands.cfg"]
        missing_files = []

        for file in required_files:
            file_path = nagios_dir / file
            if not file_path.exists():
                missing_files.append(file)
            else:
                self.add_success(f"Archivo encontrado: {file}")

        if missing_files:
            self.add_error(f"Archivos faltantes: {', '.join(missing_files)}")
            return False

        # Validar contenido de archivos
        self._validate_nagios_syntax(nagios_dir)
        self._validate_hosts_config(nagios_dir / "hosts.cfg")
        self._validate_services_config(nagios_dir / "services.cfg")
        self._validate_contacts_config(nagios_dir / "contacts.cfg")

        return len(self.errors) == 0

    def _validate_nagios_syntax(self, nagios_dir):
        """Validar sintaxis básica de archivos Nagios"""
        cfg_files = ["hosts.cfg", "services.cfg", "contacts.cfg", "commands.cfg"]

        for cfg_file in cfg_files:
            file_path = nagios_dir / cfg_file
            if not file_path.exists():
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Verificaciones básicas de sintaxis
                if "define" not in content and cfg_file != "commands.cfg":
                    self.add_warning(f"Archivo {cfg_file} parece estar vacío o mal formateado")

                # Verificar llaves de cierre
                open_braces = content.count('{')
                close_braces = content.count('}')

                if open_braces != close_braces:
                    self.add_error(f"Desbalance de llaves en {cfg_file}: {open_braces} abiertas, {close_braces} cerradas")

                # Verificar punto y coma al final
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('//') and not line.endswith(';') and '{' not in line and '}' not in line:
                        # Permitir algunas excepciones comunes
                        if not any(skip in line for skip in ['define', 'register', 'command_name', 'command_line']):
                            self.add_warning(f"Posible línea incompleta en {cfg_file}:{i}: {line[:50]}...")

            except Exception as e:
                self.add_error(f"Error al leer {cfg_file}: {e}")

    def _validate_hosts_config(self, hosts_file):
        """Validar configuración específica de hosts"""
        try:
            with open(hosts_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que haya al menos un host definido
            if "define host" not in content:
                self.add_warning("No se encontraron definiciones de host")
                return

            # Extraer nombres de hosts
            host_matches = re.findall(r'host_name\s+([^\s;]+)', content)
            if not host_matches:
                self.add_warning("No se pudieron extraer nombres de host")
            else:
                self.add_success(f"Hosts definidos: {len(host_matches)}")

                # Verificar que todos los hosts tengan address
                for host in host_matches:
                    if f"host_name {host}" in content:
                        # Buscar address correspondiente
                        host_section = self._extract_host_section(content, host)
                        if "address" not in host_section:
                            self.add_warning(f"Host {host} no tiene dirección definida")

        except Exception as e:
            self.add_error(f"Error validando hosts.cfg: {e}")

    def _validate_services_config(self, services_file):
        """Validar configuración específica de servicios"""
        try:
            with open(services_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar que haya al menos un servicio definido
            if "define service" not in content:
                self.add_warning("No se encontraron definiciones de servicio")
                return

            # Extraer servicios
            service_matches = re.findall(r'service_description\s+([^\s;]+)', content)
            if service_matches:
                self.add_success(f"Servicios definidos: {len(service_matches)}")

        except Exception as e:
            self.add_error(f"Error validando services.cfg: {e}")

    def _validate_contacts_config(self, contacts_file):
        """Validar configuración específica de contactos"""
        try:
            with open(contacts_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Verificar contactos
            contact_matches = re.findall(r'contact_name\s+([^\s;]+)', content)
            if contact_matches:
                self.add_success(f"Contactos definidos: {len(contact_matches)}")

            # Verificar emails
            email_matches = re.findall(r'email\s+([^\s;]+)', content)
            invalid_emails = [email for email in email_matches if '@' not in email]

            if invalid_emails:
                self.add_warning(f"Direcciones de email posiblemente inválidas: {invalid_emails}")

        except Exception as e:
            self.add_error(f"Error validando contacts.cfg: {e}")

    def _extract_host_section(self, content, host_name):
        """Extraer sección de configuración de un host específico"""
        # Esta es una implementación simplificada
        # En un validador más completo, se usaría un parser más sofisticado
        return content

    def validate_elastic_configs(self):
        """Validar configuraciones de Elastic Stack"""
        print("\n🔍 Validando configuración de Elastic Stack...")

        elastic_dir = self.config_dir / "elastic"
        if not elastic_dir.exists():
            self.add_error(f"Directorio de Elastic no encontrado: {elastic_dir}")
            return False

        # Validar archivos YAML
        yaml_files = ["filebeat.yml", "logstash.conf"]
        for yaml_file in yaml_files:
            file_path = elastic_dir / yaml_file
            if file_path.exists():
                self._validate_yaml_file(file_path)

        # Validar archivos JSON
        json_files = ["ingest_pipeline.json", "index_template.json", "kibana_dashboard.json", "alerts.json"]
        for json_file in json_files:
            file_path = elastic_dir / json_file
            if file_path.exists():
                self._validate_json_file(file_path)

        return len(self.errors) == 0

    def _validate_yaml_file(self, file_path):
        """Validar archivo YAML"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)

            self.add_success(f"YAML válido: {file_path.name}")

        except yaml.YAMLError as e:
            self.add_error(f"Error de sintaxis YAML en {file_path.name}: {e}")
        except Exception as e:
            self.add_error(f"Error al leer {file_path.name}: {e}")

    def _validate_json_file(self, file_path):
        """Validar archivo JSON"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)

            self.add_success(f"JSON válido: {file_path.name}")

            # Validaciones específicas por tipo de archivo
            if file_path.name == "ingest_pipeline.json":
                self._validate_ingest_pipeline(f)
            elif file_path.name == "index_template.json":
                self._validate_index_template(f)

        except json.JSONDecodeError as e:
            self.add_error(f"Error de sintaxis JSON en {file_path.name}: {e}")
        except Exception as e:
            self.add_error(f"Error al leer {file_path.name}: {e}")

    def _validate_ingest_pipeline(self, file_handle):
        """Validar pipeline de ingest específico"""
        file_handle.seek(0)  # Reiniciar lectura del archivo
        data = json.load(file_handle)

        if "processors" in data:
            processors_count = len(data["processors"])
            self.add_success(f"Pipeline con {processors_count} procesadores")

            # Verificar procesadores comunes
            processor_types = [p for p in data["processors"] if isinstance(p, dict)]
            if not processor_types:
                self.add_warning("No se encontraron procesadores válidos en el pipeline")

    def _validate_index_template(self, file_handle):
        """Validar template de índice específico"""
        file_handle.seek(0)  # Reiniciar lectura del archivo
        data = json.load(file_handle)

        if "index_patterns" in data:
            patterns = data["index_patterns"]
            self.add_success(f"Template con patrones: {patterns}")

        if "mappings" in data.get("template", {}):
            self.add_success("Template incluye definiciones de mappings")

    def validate_log_paths(self, json_file):
        """Validar que las rutas de logs sean accesibles"""
        print("\n📁 Validando rutas de logs...")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for log in data.get("logs", []):
                log_path = log.get("path", "")
                log_name = log.get("name", "desconocido")

                if log_path:
                    if os.path.exists(log_path):
                        self.add_success(f"Ruta de log válida: {log_name} -> {log_path}")
                    else:
                        self.add_warning(f"Ruta de log no existe: {log_name} -> {log_path}")
                else:
                    self.add_warning(f"Log sin ruta definida: {log_name}")

        except Exception as e:
            self.add_error(f"Error validando rutas de logs: {e}")

    def generate_validation_report(self):
        """Generar reporte completo de validación"""
        report_file = self.config_dir / "validation_report.txt"

        report_content = f"""# Reporte de Validación de Configuraciones

**Fecha de validación:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Directorio validado:** {self.config_dir}

## Resumen de Validación

### Errores Encontrados ({len(self.errors)})
"""

        if self.errors:
            report_content += "\n".join(self.errors)
        else:
            report_content += "No se encontraron errores críticos."

        report_content += f"""

### Advertencias ({len(self.warnings)})
"""

        if self.warnings:
            report_content += "\n".join(self.warnings)
        else:
            report_content += "No se encontraron advertencias."

        report_content += f"""

### Validaciones Exitosas ({len(self.success)})
"""

        if self.success:
            report_content += "\n".join(self.success)
        else:
            report_content += "No se completaron validaciones exitosamente."

        report_content += """

## Recomendaciones

"""

        if self.errors:
            report_content += """
### Acciones Críticas Requeridas:
1. Corregir todos los errores antes de desplegar
2. Verificar sintaxis de archivos de configuración
3. Probar configuración en ambiente de desarrollo
"""
        else:
            report_content += """
### Próximos Pasos:
1. Desplegar configuración en ambiente de producción
2. Verificar funcionamiento de servicios de monitorización
3. Configurar alertas y notificaciones
"""

        report_content += """

## Estado General:
"""

        if not self.errors:
            report_content += "✅ **CONFIGURACIÓN VÁLIDA** - Lista para despliegue"
        elif len(self.errors) < 3:
            report_content += "⚠️  **CONFIGURACIÓN CON ADVERTENCIAS** - Revisar antes de desplegar"
        else:
            report_content += "❌ **CONFIGURACIÓN INVÁLIDA** - Requiere correcciones"

        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)

            print(f"\n📋 Reporte de validación generado: {report_file}")
            return True

        except Exception as e:
            print(f"❌ Error generando reporte: {e}")
            return False

    def run_full_validation(self, json_file=None):
        """Ejecutar validación completa"""
        print("=" * 60)
        print("🔍 SISTEMA DE VALIDACIÓN DE CONFIGURACIONES")
        print("=" * 60)

        # Validar configuraciones de Nagios
        nagios_valid = self.validate_nagios_configs()

        # Validar configuraciones de Elastic
        elastic_valid = self.validate_elastic_configs()

        # Validar rutas de logs si se proporciona JSON
        if json_file and os.path.exists(json_file):
            self.validate_log_paths(json_file)

        # Generar reporte
        self.generate_validation_report()

        # Mostrar resumen final
        print("\n" + "=" * 60)
        print("📊 RESUMEN DE VALIDACIÓN")
        print("=" * 60)

        if not self.errors:
            print("✅ Validación exitosa: Todas las configuraciones son válidas")
            return True
        else:
            print(f"❌ Se encontraron {len(self.errors)} errores y {len(self.warnings)} advertencias")
            return False


def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validador de Configuraciones de Monitorización",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'config_dir',
        help='Directorio que contiene las configuraciones generadas'
    )

    parser.add_argument(
        '--json',
        help='Archivo JSON original para validar rutas de logs'
    )

    args = parser.parse_args()

    # Crear validador y ejecutar validación
    validator = ConfigValidator(args.config_dir)

    try:
        success = validator.run_full_validation(args.json if args.json else None)

        if success:
            print("\n🎉 ¡Validación completada exitosamente!")
            sys.exit(0)
        else:
            print("\n❌ La validación encontró problemas que requieren atención")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()