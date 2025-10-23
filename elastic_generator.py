#!/usr/bin/env python3
"""
Elastic Stack Configuration Generator
Genera configuraciones de Elastic Stack (Filebeat, Logstash, Elasticsearch, Kibana)
basadas en el JSON del formulario de monitorización
"""

import json
import os
import yaml
from datetime import datetime
from jinja2 import Template


class ElasticConfigGenerator:
    """Genera configuraciones completas de Elastic Stack desde JSON"""

    def __init__(self, json_data, output_dir="output/elastic"):
        self.data = json_data
        self.output_dir = output_dir
        self.templates_dir = "templates/elastic"

        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)

        # Mapear formatos de log a tipos de procesamiento
        self.log_format_processors = {
            "Texto plano simple": "grok",
            "Texto plano multilínea": "multiline_grok",
            "JSON estructurado": "json"
        }

        # Patrones Grok comunes
        self.common_grok_patterns = {
            "timestamp": "%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{TIME}",
            "loglevel": "(INFO|DEBUG|WARN|ERROR|FATAL|CRITICAL)",
            "username": "%{USERNAME:user}",
            "ip": "%{IP:client_ip}",
            "path": "%{URIPATH:path}",
            "method": "%{WORD:method}",
            "status_code": "%{POSINT:status_code}",
            "duration": "%{NUMBER:duration}ms",
            "db_queries": "%{NUMBER:db_queries}",
            "db_time": "%{NUMBER:db_time}ms"
        }

    def _generate_index_name(self, service_name, log_name):
        """Genera nombre de índice único"""
        service_clean = service_name.lower().replace(" ", "-").replace("_", "-")
        log_clean = log_name.lower().replace(".", "-").replace("_", "-")
        return f"{service_clean}-{log_clean}-%{YYYY.MM.dd}"

    def _create_grok_pattern(self, log_patterns):
        """Crea patrón grok basado en los patrones del log"""
        if not log_patterns:
            return "%{GREEDYDATA:message}"

        # Crear patrón compuesto basado en los campos comunes encontrados
        pattern_parts = []

        for pattern in log_patterns:
            if "TIMESTAMP" in pattern:
                pattern_parts.append("%{timestamp}")
            if "LEVEL" in pattern:
                pattern_parts.append("%{loglevel}")
            if "User:" in pattern or "USERNAME" in pattern:
                pattern_parts.append("%{username}")
            if "IP:" in pattern or "IP_ADDRESS" in pattern:
                pattern_parts.append("%{ip}")
            if "Action:" in pattern or "ACTION" in pattern:
                pattern_parts.append("Action: %{WORD:action}")
            if "Resource:" in pattern or "RESOURCE" in pattern:
                pattern_parts.append("Resource: %{URIPATH:resource}")
            if "MESSAGE" in pattern:
                pattern_parts.append("%{GREEDYDATA:message}")

        return " ".join(pattern_parts) if pattern_parts else "%{GREEDYDATA:message}"

    def generate_filebeat_config(self):
        """Genera configuración de Filebeat para recolecta logs"""
        filebeat_config = {
            "filebeat.inputs": [],
            "output.elasticsearch": {
                "hosts": ["localhost:9200"],
                "index": "filebeat-%{[agent.version]}-%{[fields.service_name]}-%{+yyyy.MM.dd}"
            },
            "setup.ilm.enabled": False,
            "setup.template.enabled": True,
            "processors": [
                {
                    "add_host_metadata": {
                        "when.not.contains.tags": "forwarded"
                    }
                },
                {
                    "add_cloud_metadata": None
                },
                {
                    "add_docker_metadata": None
                },
                {
                    "add_kubernetes_metadata": None
                }
            ]
        }

        # Crear inputs para cada log
        for log in self.data.get("logs", []):
            log_name = log.get("name", "")
            log_path = log.get("path", "")
            log_format = log.get("format", "Texto plano simple")

            # Crear campos personalizados para el servicio
            service_name = self.data.get("identification", {}).get("service_name", "unknown")
            fields = {
                "service_name": service_name.lower().replace(" ", "_"),
                "log_type": log_name.replace(".", "_"),
                "environment": "default"
            }

            # Agregar información de hosts si está disponible
            hosts_info = []
            for env in self.data.get("envs", []):
                for host in env.get("hosts", []):
                    host_info = {
                        "type": host.get("type", "host"),
                        "identifier": host.get("identifier", ""),
                        "address": host.get("address", host.get("identifier", ""))
                    }
                    hosts_info.append(host_info)
            if hosts_info:
                fields["hosts"] = hosts_info

            input_config = {
                "type": "log",
                "paths": [log_path],
                "fields": fields,
                "tags": [service_name.lower(), log_name.replace(".", "_")],
                "encoding": "utf-8"
            }

            # Configurar procesadores según formato
            if log_format == "Texto plano multilínea":
                input_config["multiline.pattern"] = "^\\["
                input_config["multiline.negate"] = True
                input_config["multiline.match"] = "after"
            elif log_format == "JSON estructurado":
                input_config["json.keys_under_root"] = True
                input_config["json.overwrite_keys"] = True

            filebeat_config["filebeat.inputs"].append(input_config)

        return filebeat_config

    def generate_logstash_config(self):
        """Genera configuración de Logstash para procesar logs"""
        logstash_config = {
            "input": {
                "beats": {
                    "port": 5044
                }
            },
            "filter": [],
            "output": {
                "elasticsearch": {
                    "hosts": ["localhost:9200"],
                    "index": "%{[@metadata][beat]}-%{[@metadata][version]}-%{[fields][service_name]}-%{+YYYY.MM.dd}"
                }
            }
        }

        service_name = self.data.get("identification", {}).get("service_name", "unknown")

        # Crear filtros para cada tipo de log
        for log in self.data.get("logs", []):
            log_name = log.get("name", "")
            log_format = log.get("format", "Texto plano simple")
            patterns = log.get("patterns", [])

            if log_format == "JSON estructurado":
                # Procesamiento JSON
                json_filter = {
                    "if": f"[fields][log_type] == \"{log_name.replace('.', '_')}\"",
                    "json": {
                        "source": "message",
                        "target": "json_data"
                    }
                }
                logstash_config["filter"].append(json_filter)

            elif log_format in ["Texto plano simple", "Texto plano multilínea"]:
                # Procesamiento Grok
                grok_pattern = self._create_grok_pattern(patterns)

                grok_filter = {
                    "if": f"[fields][log_type] == \"{log_name.replace('.', '_')}\"",
                    "grok": {
                        "match": {"message": grok_pattern},
                        "patterns_dir": ["/usr/share/logstash/patterns"]
                    }
                }
                logstash_config["filter"].append(grok_filter)

            # Agregar campos comunes a todos los logs
            mutate_filter = {
                "if": f"[fields][service_name] == \"{service_name.lower().replace(' ', '_')}\"",
                "mutate": {
                    "add_field": {
                        "service": service_name,
                        "log_name": log_name,
                        "processed_at": "%{@timestamp}"
                    }
                }
            }
            logstash_config["filter"].append(mutate_filter)

        return logstash_config

    def generate_ingest_pipeline(self):
        """Genera pipeline de ingest para Elasticsearch"""
        service_name = self.data.get("identification", {}).get("service_name", "unknown")

        pipeline = {
            "description": f"Pipeline de procesamiento para {service_name}",
            "processors": [
                {
                    "set": {
                        "field": "_meta.service_name",
                        "value": service_name
                    }
                },
                {
                    "set": {
                        "field": "_meta.generated_at",
                        "value": datetime.now().isoformat()
                    }
                }
            ]
        }

        # Procesadores específicos por tipo de log
        for log in self.data.get("logs", []):
            log_name = log.get("name", "")
            log_format = log.get("format", "Texto plano simple")

            if log_format == "JSON estructurado":
                # Procesador para JSON
                json_processor = {
                    "json": {
                        "field": "message",
                        "target_field": "json_data",
                        "ignore_failure": True
                    }
                }
                pipeline["processors"].append(json_processor)

            # Procesador de fecha común
            date_processor = {
                "date": {
                    "field": "@timestamp",
                    "formats": ["ISO8601", "yyyy-MM-dd HH:mm:ss"],
                    "ignore_failure": True
                }
            }
            pipeline["processors"].append(date_processor)

        return pipeline

    def generate_index_template(self):
        """Genera template de índice para Elasticsearch"""
        service_name = self.data.get("identification", {}).get("service_name", "unknown")

        template = {
            "index_patterns": [f"{service_name.lower().replace(' ', '-')}*-*"],
            "template": {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                    "index.lifecycle.name": "default_policy"
                },
                "mappings": {
                    "properties": {
                        "@timestamp": {
                            "type": "date"
                        },
                        "message": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "service": {
                            "type": "keyword"
                        },
                        "log_name": {
                            "type": "keyword"
                        },
                        "fields": {
                            "properties": {
                                "service_name": {"type": "keyword"},
                                "log_type": {"type": "keyword"},
                                "environment": {"type": "keyword"}
                            }
                        }
                    }
                }
            }
        }

        # Agregar campos específicos según los patrones de logs
        for log in self.data.get("logs", []):
            patterns = log.get("patterns", [])

            if any("LEVEL" in pattern for pattern in patterns):
                template["template"]["mappings"]["properties"]["level"] = {"type": "keyword"}

            if any("User:" in pattern or "USERNAME" in pattern for pattern in patterns):
                template["template"]["mappings"]["properties"]["user"] = {"type": "keyword"}

            if any("IP:" in pattern or "IP_ADDRESS" in pattern for pattern in patterns):
                template["template"]["mappings"]["properties"]["client_ip"] = {"type": "ip"}

            if any("Duration:" in pattern or "DURATION" in pattern for pattern in patterns):
                template["template"]["mappings"]["properties"]["duration"] = {"type": "integer"}

            if any("DB_Queries:" in pattern or "QUERIES" in pattern for pattern in patterns):
                template["template"]["mappings"]["properties"]["db_queries"] = {"type": "integer"}

        return template

    def generate_kibana_dashboards(self):
        """Genera configuración básica de dashboards para Kibana"""
        service_name = self.data.get("identification", {}).get("service_name", "unknown")

        dashboard = {
            "id": f"{service_name.lower().replace(' ', '_')}_overview",
            "title": f"{service_name} - Overview",
            "description": f"Dashboard general para el servicio {service_name}",
            "panels": []
        }

        # Panel de logs recientes
        logs_panel = {
            "id": 1,
            "type": "search",
            "title": "Logs Recientes",
            "query": {
                "query": f"fields.service_name: {service_name.lower().replace(' ', '_')}",
                "language": "kuery"
            }
        }
        dashboard["panels"].append(logs_panel)

        # Panel de errores por nivel
        if any("LEVEL" in log.get("patterns", []) for log in self.data.get("logs", [])):
            error_panel = {
                "id": 2,
                "type": "histogram",
                "title": "Errores por Nivel",
                "field": "level",
                "interval": "auto"
            }
            dashboard["panels"].append(error_panel)

        # Panel de actividad por usuario (si aplica)
        if any("User:" in str(patterns) or "USERNAME" in str(patterns)
               for log in self.data.get("logs", [])
               for patterns in [log.get("patterns", [])]):
            user_panel = {
                "id": 3,
                "type": "pie",
                "title": "Actividad por Usuario",
                "field": "user"
            }
            dashboard["panels"].append(user_panel)

        return dashboard

    def generate_alerts_config(self):
        """Genera configuración de alertas basada en patrones críticos"""
        service_name = self.data.get("identification", {}).get("service_name", "unknown")

        alerts = []

        # Crear alerta para errores críticos
        critical_alert = {
            "id": f"{service_name.lower().replace(' ', '_')}_critical_errors",
            "name": f"Errores Críticos - {service_name}",
            "description": f"Alerta cuando se detectan errores críticos en {service_name}",
            "condition": {
                "query": {
                    "match": {
                        "fields.service_name": service_name.lower().replace(" ", "_")
                    }
                },
                "filter": [
                    {"term": {"level": "ERROR"}},
                    {"term": {"level": "CRITICAL"}},
                    {"term": {"level": "FATAL"}}
                ]
            },
            "actions": [
                {
                    "type": "email",
                    "recipients": [resp.get("email") for resp in self.data.get("responsables", [])]
                }
            ]
        }
        alerts.append(critical_alert)

        # Crear alertas específicas basadas en patrones de logs
        for log in self.data.get("logs", []):
            log_name = log.get("name", "")
            patterns = log.get("patterns", [])

            # Buscar patrones que indiquen problemas
            for pattern in patterns:
                if any(keyword in pattern.upper() for keyword in ["ERROR", "FAILED", "EXCEPTION", "CRITICAL"]):
                    pattern_alert = {
                        "id": f"{service_name.lower().replace(' ', '_')}_{log_name.replace('.', '_')}_issues",
                        "name": f"Problemas en {log_name} - {service_name}",
                        "description": f"Alerta para patrones problemáticos en {log_name}",
                        "condition": {
                            "query": {
                                "match": {
                                    "fields.log_type": log_name.replace(".", "_")
                                }
                            }
                        }
                    }
                    alerts.append(pattern_alert)

        return alerts

    def generate_all_configs(self):
        """Genera todas las configuraciones de Elastic Stack"""
        print("Generando configuraciones de Elastic Stack...")

        # Generar cada tipo de configuración
        filebeat_cfg = self.generate_filebeat_config()
        logstash_cfg = self.generate_logstash_config()
        pipeline_cfg = self.generate_ingest_pipeline()
        template_cfg = self.generate_index_template()
        dashboard_cfg = self.generate_kibana_dashboards()
        alerts_cfg = self.generate_alerts_config()

        # Guardar archivos individuales
        files_to_save = [
            ("filebeat.yml", yaml.dump(filebeat_cfg, default_flow_style=False, allow_unicode=True)),
            ("logstash.conf", yaml.dump(logstash_cfg, default_flow_style=False, allow_unicode=True)),
            ("ingest_pipeline.json", json.dumps(pipeline_cfg, indent=2, ensure_ascii=False)),
            ("index_template.json", json.dumps(template_cfg, indent=2, ensure_ascii=False)),
            ("kibana_dashboard.json", json.dumps(dashboard_cfg, indent=2, ensure_ascii=False)),
            ("alerts.json", json.dumps(alerts_cfg, indent=2, ensure_ascii=False))
        ]

        saved_files = []
        for filename, content in files_to_save:
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            saved_files.append(filepath)
            print(f"OK Archivo generado: {filepath}")

        return saved_files, {
            "filebeat": filebeat_cfg,
            "logstash": logstash_cfg,
            "pipeline": pipeline_cfg,
            "template": template_cfg,
            "dashboard": dashboard_cfg,
            "alerts": alerts_cfg
        }


def generate_elastic_from_json(json_file, output_dir="output/elastic"):
    """Función principal para generar configuración de Elastic desde JSON"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        generator = ElasticConfigGenerator(data, output_dir)
        files, metadata = generator.generate_all_configs()

        print(f"\nOK Configuracion de Elastic Stack generada exitosamente!")
        print(f"OK Archivos generados: {len(files)}")
        print(f"OK Logs configurados: {len(data.get('logs', []))}")
        print(f"OK Alertas configuradas: {len(metadata['alerts'])}")

        return files, metadata

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo JSON: {json_file}")
        return [], {}
    except json.JSONDecodeError as e:
        print(f"Error: Error de formato JSON: {e}")
        return [], {}
    except Exception as e:
        print(f"Error inesperado: {e}")
        return [], {}


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Uso: python elastic_generator.py <archivo.json>")
        sys.exit(1)

    json_file = sys.argv[1]
    generate_elastic_from_json(json_file)