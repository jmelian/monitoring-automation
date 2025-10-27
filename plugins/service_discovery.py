#!/usr/bin/env python3
"""
Service Discovery Module
Módulo de auto-detección de servicios y dependencias
"""

import json
import socket
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import logging

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Advertencia: requests no disponible, algunas funciones de discovery estarán limitadas")


class ServiceDiscovery:
    """Clase para auto-detección de servicios"""

    def __init__(self, orchestrator_config: Dict[str, Any]):
        self.orchestrator_config = orchestrator_config
        self.logger = logging.getLogger('service_discovery')
        self.orchestrator = orchestrator_config.get('orchestrator', 'none')

    def discover_services(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Descubre servicios automáticamente basado en el orquestador

        Args:
            base_config: Configuración base del JSON

        Returns:
            Configuración enriquecida con servicios detectados
        """
        self.logger.info(f"Iniciando auto-detección de servicios con orquestador: {self.orchestrator}")
        if self.orchestrator == 'docker':
            result = self._discover_docker_services(base_config)
        elif self.orchestrator == 'kubernetes':
            result = self._discover_k8s_services(base_config)
        elif self.orchestrator == 'docker-compose':
            result = self._discover_docker_compose_services(base_config)
        else:
            self.logger.info("No se detectó orquestador, usando configuración manual")
            result = base_config

        self.logger.info("Auto-detección de servicios completada")
        return result

    def _discover_docker_services(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Descubre servicios en Docker"""
        self.logger.info("Iniciando auto-detección de servicios Docker...")
        try:
            import docker
            client = docker.from_env()
            self.logger.debug("Cliente Docker conectado")

            # Obtener contenedores corriendo
            containers = client.containers.list()
            self.logger.info(f"Contenedores encontrados: {len(containers)}")

            discovered_services = []
            discovered_hosts = []

            for container in containers:
                self.logger.debug(f"Analizando contenedor: {container.name}")
                service_info = self._analyze_container(container)
                if service_info:
                    discovered_services.append(service_info)
                    self.logger.debug(f"Servicio detectado: {service_info.get('name')}")

                host_info = self._extract_host_info(container)
                if host_info:
                    discovered_hosts.append(host_info)
                    self.logger.debug(f"Host detectado: {host_info.get('identifier')}")

            # Enriquecer configuración
            enriched_config = base_config.copy()
            self.logger.info(f"Servicios descubiertos: {len(discovered_services)}, Hosts descubiertos: {len(discovered_hosts)}")

            if discovered_services:
                existing_deps = enriched_config.get('dependencies', [])
                existing_names = {dep.get('name', '') for dep in existing_deps}
                new_deps = [dep for dep in discovered_services if dep.get('name', '') not in existing_names]
                enriched_config['dependencies'] = existing_deps + new_deps
                self.logger.info(f"Dependencias añadidas: {len(new_deps)}")

            # Actualizar hosts si es necesario
            if discovered_hosts:
                for env in enriched_config.get('envs', []):
                    existing_host_ids = {host.get('identifier', '') for host in env.get('hosts', [])}
                    new_hosts = [host for host in discovered_hosts if host.get('identifier', '') not in existing_host_ids]
                    env['hosts'].extend(new_hosts)
                    self.logger.info(f"Hosts añadidos al entorno {env.get('name')}: {len(new_hosts)}")

            return enriched_config

        except ImportError:
            self.logger.warning("Docker SDK no disponible, omitiendo auto-detección")
            return base_config
        except Exception as e:
            self.logger.error(f"Error en auto-detección Docker: {e}")
            return base_config

    def _discover_k8s_services(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Descubre servicios en Kubernetes"""
        try:
            from kubernetes import client, config

            # Cargar configuración de K8s
            kubeconfig = self.orchestrator_config.get('kubeconfig')
            if kubeconfig:
                config.load_kube_config(config_file=kubeconfig)
            else:
                config.load_incluster_config()

            v1 = client.CoreV1Api()

            # Obtener servicios
            services = v1.list_service_for_all_namespaces().items
            pods = v1.list_pod_for_all_namespaces().items

            discovered_services = []
            discovered_hosts = []

            for service in services:
                service_info = self._analyze_k8s_service(service)
                if service_info:
                    discovered_services.append(service_info)

            for pod in pods:
                host_info = self._extract_k8s_host_info(pod)
                if host_info:
                    discovered_hosts.append(host_info)

            # Enriquecer configuración similar a Docker
            enriched_config = base_config.copy()

            if discovered_services:
                existing_deps = enriched_config.get('dependencies', [])
                existing_names = {dep.get('name', '') for dep in existing_deps}
                new_deps = [dep for dep in discovered_services if dep.get('name', '') not in existing_names]
                enriched_config['dependencies'] = existing_deps + new_deps

            return enriched_config

        except ImportError:
            self.logger.warning("Kubernetes SDK no disponible, omitiendo auto-detección")
            return base_config
        except Exception as e:
            self.logger.error(f"Error en auto-detección Kubernetes: {e}")
            return base_config

    def _discover_docker_compose_services(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Descubre servicios en Docker Compose"""
        try:
            import docker
            client = docker.from_env()

            # Buscar contenedores con labels de compose
            containers = client.containers.list(filters={'label': 'com.docker.compose.service'})

            discovered_services = []

            for container in containers:
                service_info = self._analyze_compose_service(container)
                if service_info:
                    discovered_services.append(service_info)

            # Enriquecer configuración
            enriched_config = base_config.copy()

            if discovered_services:
                existing_deps = enriched_config.get('dependencies', [])
                existing_names = {dep.get('name', '') for dep in existing_deps}
                new_deps = [dep for dep in discovered_services if dep.get('name', '') not in existing_names]
                enriched_config['dependencies'] = existing_deps + new_deps

            return enriched_config

        except Exception as e:
            self.logger.error(f"Error en auto-detección Docker Compose: {e}")
            return base_config

    def _analyze_container(self, container) -> Optional[Dict[str, Any]]:
        """Analiza un contenedor Docker y extrae información de servicio"""
        try:
            self.logger.debug(f"Analizando contenedor: {container.name}")
            container_info = container.attrs
            config = container_info.get('Config', {})
            network_settings = container_info.get('NetworkSettings', {})

            # Extraer puertos expuestos
            ports = config.get('ExposedPorts', {})
            if not ports:
                self.logger.debug(f"Contenedor {container.name} no tiene puertos expuestos")
                return None

            # Determinar protocolo basado en puertos
            service_info = {
                'name': container.name,
                'type': 'Contenedor',
                'nature': 'Interna',
                'impact': 'Alto',
                'check_protocol': 'docker'
            }

            # Asignar puerto y protocolo
            port_mappings = network_settings.get('Ports', {})
            if port_mappings:
                for container_port, host_bindings in port_mappings.items():
                    if host_bindings:
                        port_num = container_port.split('/')[0]
                        protocol = container_port.split('/')[1] if '/' in container_port else 'tcp'

                        service_info.update({
                            'port': port_num,
                            'check_protocol': protocol if protocol in ['tcp', 'udp'] else 'tcp'
                        })
                        self.logger.debug(f"Puerto detectado: {port_num}/{protocol}")
                        break

            # Parámetros específicos para Docker
            service_info['check_params'] = {
                'container_name': container.name,
                'check_type': 'running'
            }

            # Intentar detectar tipo de servicio basado en imagen
            image = config.get('Image', '').lower()
            self.logger.debug(f"Imagen del contenedor: {image}")
            if 'nginx' in image:
                service_info.update({
                    'type': 'Web Server',
                    'effect': 'Servidor web no disponible'
                })
            elif 'postgres' in image or 'mysql' in image:
                service_info.update({
                    'type': 'Base de datos',
                    'effect': 'Base de datos no accesible',
                    'check_protocol': 'tcp'
                })
            elif 'redis' in image:
                service_info.update({
                    'type': 'Cache',
                    'effect': 'Cache no disponible'
                })

            # Si es HTTP/HTTPS, analizar respuesta para mejor detección
            if service_info.get('check_protocol') == 'http':
                host_address = container.name  # Usar nombre como host para análisis
                self.logger.debug(f"Analizando servicio HTTP en {host_address}:{port_num}")
                self._enhance_http_service_info(service_info, host_address, port_num)

            self.logger.debug(f"Servicio analizado: {service_info.get('name')} ({service_info.get('type')})")
            return service_info

        except Exception as e:
            self.logger.warning(f"Error analizando contenedor {container.name}: {e}")
            return None

    def _enhance_http_service_info(self, service_info: Dict[str, Any], host: str, port: str):
        """Mejora la información de servicio HTTP analizando la respuesta"""
        if not REQUESTS_AVAILABLE:
            self.logger.debug("Requests no disponible, omitiendo análisis HTTP")
            return

        try:
            self.logger.debug(f"Mejorando información HTTP para {host}:{port}")
            # Construir URL base
            scheme = 'https' if port == '443' else 'http'
            base_url = f"{scheme}://{host}:{port}"
            self.logger.debug(f"URL base: {base_url}")

            # Detectar health endpoints y analizar
            health_endpoints = self.detect_health_endpoints(base_url)
            if health_endpoints:
                self.logger.debug(f"Health endpoints encontrados: {len(health_endpoints)}")
                # Usar el primero encontrado como endpoint principal
                primary_endpoint = health_endpoints[0]
                service_info['check_params']['url'] = primary_endpoint['endpoint'].replace(base_url, '')
                service_info['check_params']['expected_format'] = primary_endpoint['format']
                self.logger.debug(f"Endpoint primario: {primary_endpoint['endpoint']} ({primary_endpoint['format']})")

                # Si es JSON, intentar inferir más detalles
                if primary_endpoint['format'] == 'JSON':
                    try:
                        response = requests.get(primary_endpoint['endpoint'], timeout=5)
                        data = response.json()
                        self.logger.debug(f"Respuesta JSON analizada: {len(data)} campos")
                        # Buscar campos comunes para inferir tipo de servicio
                        if 'status' in data or 'health' in data:
                            service_info['type'] = 'Health Check Service'
                            service_info['effect'] = 'Servicio de health check no disponible'
                        elif 'database' in str(data).lower() or 'db' in str(data).lower():
                            service_info['type'] = 'Database API'
                            service_info['effect'] = 'API de base de datos no accesible'
                    except Exception as e:
                        self.logger.debug(f"Error analizando respuesta JSON: {e}")

            # Analizar respuesta raíz para más inferencia
            try:
                self.logger.debug(f"Analizando respuesta raíz: {base_url}")
                response = requests.get(base_url, timeout=5)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    text = response.text.lower()
                    self.logger.debug(f"Content-type: {content_type}, Status: {response.status_code}")

                    # Inferir tipo basado en content-type y contenido
                    if 'text/html' in content_type:
                        if 'nginx' in text or 'welcome' in text:
                            service_info['type'] = 'Nginx Web Server'
                        elif 'apache' in text:
                            service_info['type'] = 'Apache Web Server'
                        else:
                            service_info['type'] = 'Web Server'
                        service_info['effect'] = 'Servidor web no disponible'
                    elif 'application/json' in content_type:
                        service_info['type'] = 'API Service'
                        service_info['effect'] = 'API no disponible'
                        # Añadir expected_status si no es 200 por defecto
                        if response.status_code != 200:
                            service_info['check_params']['expected_status'] = response.status_code
                    else:
                        service_info['type'] = 'Generic HTTP Service'
                        service_info['effect'] = 'Servicio HTTP no disponible'

                    self.logger.debug(f"Tipo de servicio inferido: {service_info.get('type')}")
                else:
                    self.logger.debug(f"Respuesta no exitosa: {response.status_code}")

            except Exception as e:
                self.logger.debug(f"Error analizando respuesta raíz: {e}")

        except Exception as e:
            self.logger.debug(f"Error mejorando info HTTP para {host}:{port}: {e}")

    def _analyze_k8s_service(self, service) -> Optional[Dict[str, Any]]:
        """Analiza un servicio de Kubernetes"""
        try:
            metadata = service.metadata
            spec = service.spec

            service_info = {
                'name': metadata.name,
                'type': 'Servicio K8s',
                'nature': 'Interna',
                'impact': 'Alto',
                'check_protocol': 'kubernetes'
            }

            # Extraer puertos
            ports = spec.ports
            if ports:
                port = ports[0].port
                service_info['port'] = str(port)

                # Determinar protocolo
                if ports[0].name and 'http' in ports[0].name.lower():
                    service_info['check_protocol'] = 'http'
                else:
                    service_info['check_protocol'] = 'tcp'

            # Parámetros específicos para K8s
            service_info['check_params'] = {
                'resource_type': 'service',
                'resource_name': metadata.name,
                'namespace': metadata.namespace or 'default',
                'check_type': 'status'
            }

            # Si es HTTP, mejorar detección
            if service_info.get('check_protocol') == 'http':
                # Usar el nombre del servicio como host para análisis
                host = metadata.name
                self._enhance_http_service_info(service_info, host, str(port))

            return service_info

        except Exception as e:
            self.logger.warning(f"Error analizando servicio K8s {service.metadata.name}: {e}")
            return None

    def _analyze_compose_service(self, container) -> Optional[Dict[str, Any]]:
        """Analiza un servicio de Docker Compose"""
        try:
            labels = container.labels
            service_name = labels.get('com.docker.compose.service')

            if not service_name:
                return None

            # Similar al análisis de Docker normal pero con info de compose
            service_info = self._analyze_container(container)
            if service_info:
                service_info['name'] = f"{service_name} (Compose)"
                service_info['check_params']['compose_service'] = service_name

            return service_info

        except Exception as e:
            self.logger.warning(f"Error analizando servicio Compose {container.name}: {e}")
            return None

    def _extract_host_info(self, container) -> Optional[Dict[str, Any]]:
        """Extrae información de host desde contenedor Docker"""
        return {
            'type': 'container',
            'identifier': container.name,
            'address': container.name  # En Docker, usar nombre como dirección
        }

    def _extract_k8s_host_info(self, pod) -> Optional[Dict[str, Any]]:
        """Extrae información de host desde pod de Kubernetes"""
        return {
            'type': 'pod',
            'identifier': pod.metadata.name,
            'address': pod.status.pod_ip or pod.metadata.name
        }

    def scan_ports(self, host: str, port_range: Tuple[int, int] = (1, 1024)) -> List[Dict[str, Any]]:
        """
        Escanea puertos abiertos en un host

        Args:
            host: Host a escanear
            port_range: Rango de puertos (inicio, fin)

        Returns:
            Lista de servicios detectados
        """
        discovered_services = []

        for port in range(port_range[0], port_range[1] + 1):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))

                if result == 0:
                    # Puerto abierto, intentar identificar servicio
                    service = self._identify_service_by_port(host, port)
                    if service:
                        discovered_services.append(service)

                sock.close()

            except:
                continue

        return discovered_services

    def _identify_service_by_port(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Identifica servicio basado en puerto"""
        common_ports = {
            22: ('SSH', 'tcp'),
            80: ('HTTP', 'http'),
            443: ('HTTPS', 'http'),
            3306: ('MySQL', 'tcp'),
            5432: ('PostgreSQL', 'tcp'),
            6379: ('Redis', 'tcp'),
            8080: ('HTTP Alt', 'http'),
            8443: ('HTTPS Alt', 'http')
        }

        if port in common_ports:
            service_name, protocol = common_ports[port]
            return {
                'name': f'{service_name} (puerto {port})',
                'type': service_name,
                'nature': 'Interna',
                'impact': 'Alto',
                'port': str(port),
                'check_protocol': protocol,
                'effect': f'Servicio {service_name} no disponible'
            }

        return None

    def detect_health_endpoints(self, base_url: str) -> List[Dict[str, Any]]:
        """
        Detecta automáticamente endpoints de health

        Args:
            base_url: URL base del servicio

        Returns:
            Lista de endpoints de health encontrados
        """
        if not REQUESTS_AVAILABLE:
            self.logger.warning("requests no disponible, omitiendo detección de health endpoints")
            return []

        health_paths = [
            '/health',
            '/healthcheck',
            '/status',
            '/api/health',
            '/actuator/health',
            '/health/ready',
            '/health/live'
        ]

        found_endpoints = []
        self.logger.debug(f"Buscando health endpoints en: {base_url}")

        for path in health_paths:
            try:
                url = f"{base_url.rstrip('/')}{path}"
                self.logger.debug(f"Probando endpoint: {url}")
                response = requests.get(url, timeout=5)

                if response.status_code == 200:
                    format_detected = self._detect_response_format(response)
                    found_endpoints.append({
                        'endpoint': url,
                        'format': format_detected,
                        'status_code': response.status_code
                    })
                    self.logger.debug(f"Endpoint encontrado: {url} ({format_detected})")

            except Exception as e:
                self.logger.debug(f"Endpoint no disponible: {url} - {e}")
                continue

        self.logger.debug(f"Total endpoints encontrados: {len(found_endpoints)}")
        return found_endpoints

    def _detect_response_format(self, response: requests.Response) -> str:
        """Detecta formato de respuesta de health check"""
        try:
            response.json()
            return 'JSON'
        except:
            if '<?xml' in response.text.lower():
                return 'XML'
            else:
                return 'Texto'


# Función de conveniencia
def discover_services(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función principal para descubrimiento de servicios

    Args:
        config: Configuración completa del servicio

    Returns:
        Configuración enriquecida
    """
    logger = logging.getLogger('ServiceDiscovery')
    logger.info("Iniciando descubrimiento de servicios para todos los entornos")

    # Por cada entorno, ejecutar discovery
    envs = config.get('envs', [])
    logger.debug(f"Procesando {len(envs)} entornos")

    for i, env in enumerate(envs):
        env_name = env.get('name', f'env_{i}')
        orchestrator = env.get('orchestrator', 'none')
        logger.info(f"Procesando entorno {i+1}/{len(envs)}: {env_name} (orquestador: {orchestrator})")

        orchestrator_config = {
            'orchestrator': orchestrator,
            'config': env.get('orchestrator_config', {})
        }

        discovery = ServiceDiscovery(orchestrator_config)
        config = discovery.discover_services(config)

    logger.info("Descubrimiento de servicios completado para todos los entornos")
    return config