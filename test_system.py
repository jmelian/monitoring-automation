#!/usr/bin/env python3
"""
Test System
Script de demostración del sistema de automatización de monitorización
"""

import json
import os
from pathlib import Path
from monitoring_automator import MonitoringAutomator
from validate_configs import ConfigValidator


def create_test_json():
    """Crear archivo JSON de prueba basado en el ejemplo proporcionado"""
    test_json = {
        "identification": {
            "service_name": "Gestión de formación",
            "service_desc": "Plataforma de gestión de formación",
            "priority": "Baja"
        },
        "tech_stack": [
            {
                "technology": "Django",
                "version": "5.2.3"
            },
            {
                "technology": "Nginx",
                "version": "latest"
            },
            {
                "technology": "PostgreSQL",
                "version": "17"
            }
        ],
        "responsables": [
            {
                "nombre": "Javier Melián",
                "email": "jmelher@contactel.es"
            }
        ],
        "dependencies": [
            {
                "name": "LDAP",
                "type": "Autenticación",
                "nature": "Externa",
                "impact": "Alto",
                "port": "5032",
                "check_protocol": "tcp",
                "effect": "Usuarios no pueden autentificarse",
                "affected_services": [
                    "Core"
                ]
            },
            {
                "name": "Base de datos",
                "type": "Base de datos",
                "nature": "Interna",
                "impact": "Crítico",
                "port": "8082",
                "check_protocol": "tcp",
                "effect": "",
                "affected_services": []
            }
        ],
        "logs": [
            {
                "name": "formacion.log",
                "path": "/var/log/formacion/formacion.log",
                "format": "Texto plano simple",
                "retention_method": "tamano",
                "retention_value": "10MB, 5 backups",
                "patterns": [
                    "[TIMESTAMP] LEVEL [MODULE:LINE] FUNCTION - User:USERNAME IP:IP_ADDRESS Action:ACTION Resource:RESOURCE - MESSAGE"
                ]
            },
            {
                "name": "security.log",
                "path": "/var/log/formacion/security.log",
                "format": "Texto plano simple",
                "retention_method": "tamano",
                "retention_value": "10MB, 10 backups",
                "patterns": [
                    "[SECURITY] TIMESTAMP LEVEL - User:USERNAME IP:IP_ADDRESS Action:ACTION MESSAGE"
                ]
            }
        ],
        "centralized_logs": "Sí",
        "health_api": True,
        "health_api_details": {
            "endpoint": "http://xwiki.contactel.es:8082/formacion/api/health/",
            "format": "JSON",
            "fields": [],
            "auth": "none",
            "interval_sec": 30
        },
        "envs": [
            {
                "name": "EXP",
                "desc": "Producción",
                "location": "xwiki.contactel.es",
                "hosts": [
                    {
                        "type": "container",
                        "identifier": "nginx_proxy"
                    },
                    {
                        "type": "container",
                        "identifier": "django_app"
                    },
                    {
                        "type": "container",
                        "identifier": "postgres_db"
                    }
                ]
            }
        ],
        "notes": "Configuración de prueba del sistema de automatización"
    }

    # Crear directorio de prueba
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)

    # Guardar JSON de prueba
    json_file = test_dir / "test_service.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(test_json, f, indent=2, ensure_ascii=False)

    print(f"[OK] Archivo JSON de prueba creado: {json_file}")
    return str(json_file)


def run_test():
    """Ejecutar prueba completa del sistema"""
    print("=" * 60)
    print("TEST DEL SISTEMA DE AUTOMATIZACION")
    print("=" * 60)

    # Crear JSON de prueba
    json_file = create_test_json()

    # Ejecutar automatizador
    print("\nEjecutando generacion de configuraciones...")
    automator = MonitoringAutomator("test_output")
    success = automator.generate_monitoring_configs(json_file)

    if not success:
        print("[ERROR] Error en la generacion de configuraciones")
        return False

    # Encontrar directorio de ejecución más reciente
    test_output_dir = Path("test_output")
    execution_dirs = [d for d in test_output_dir.iterdir() if d.is_dir() and d.name.startswith("execution_")]
    if not execution_dirs:
        print("[ERROR] No se encontro directorio de ejecucion")
        return False

    latest_execution = max(execution_dirs, key=lambda x: x.stat().st_mtime)

    # Ejecutar validación
    print(f"\nEjecutando validacion en: {latest_execution}")
    validator = ConfigValidator(latest_execution)
    validation_success = validator.run_full_validation(json_file)

    # Mostrar resultados finales
    print("\n" + "=" * 60)
    print("📊 RESULTADOS DE LA PRUEBA")
    print("=" * 60)

    if success and validation_success:
        print("PRUEBA COMPLETADA EXITOSAMENTE!")
        print("\n📋 Resumen de archivos generados:")

        # Listar archivos generados
        for file_path in latest_execution.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(latest_execution)
                size = file_path.stat().st_size
                print(f"   • {relative_path} ({size} bytes)")

        print("\nConsulta el archivo README.md generado para instrucciones de despliegue")
        print(f"Ubicacion: {latest_execution / 'README.md'}")

        return True
    else:
        print("[ERROR] La prueba encontro problemas:")
        if not success:
            print("   - Error en generacion de configuraciones")
        if not validation_success:
            print("   - Error en validacion de configuraciones")
        return False


def cleanup_test():
    """Limpiar archivos de prueba"""
    import shutil

    test_dir = Path("test_output")
    if test_dir.exists():
        print(f"\n🗑️  Limpiando archivos de prueba: {test_dir}")
        shutil.rmtree(test_dir)
        print("[OK] Archivos de prueba eliminados")
    else:
        print("\n🗑️  No hay archivos de prueba que limpiar")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Script de prueba del sistema de automatización",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Eliminar archivos de prueba después de ejecutar'
    )

    args = parser.parse_args()

    try:
        success = run_test()

        if args.cleanup:
            cleanup_test()

        if success:
            print("\n[OK] Prueba completada exitosamente")
            exit(0)
        else:
            print("\n[ERROR] La prueba encontro problemas")
            exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        if args.cleanup:
            cleanup_test()
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error inesperado: {e}")
        if args.cleanup:
            cleanup_test()
        exit(1)