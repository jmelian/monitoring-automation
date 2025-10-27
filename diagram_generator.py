#!/usr/bin/env python3
"""
Architecture Diagram Generator
Genera diagramas de arquitectura automáticamente desde configuraciones JSON de monitorización
"""

import json
import sys
from typing import Dict, Any, List


class ArchitectureDiagramGenerator:
    """Genera diagramas de arquitectura desde JSON de monitorización"""

    def __init__(self):
        self.node_counter = 0
        self.nodes = {}
        self.edges = []

    def _get_next_node_id(self) -> str:
        """Obtiene el siguiente ID de nodo"""
        self.node_counter += 1
        return chr(64 + self.node_counter)  # A, B, C, etc.

    def _add_node(self, label: str, node_type: str = "component") -> str:
        """Añade un nodo al diagrama"""
        node_id = self._get_next_node_id()
        self.nodes[node_id] = {
            'label': label,
            'type': node_type
        }
        return node_id

    def _add_edge(self, from_node: str, to_node: str) -> None:
        """Añade una conexión entre nodos"""
        self.edges.append((from_node, to_node))

    def _format_node_label(self, text: str, details: str = "") -> str:
        """Formatea etiqueta de nodo para Mermaid"""
        # Remove special characters that cause parsing issues
        clean_text = text.replace("ó", "o").replace("á", "a").replace("é", "e").replace("í", "i").replace("ú", "u")
        clean_text = clean_text.replace("ñ", "n").replace("¿", "").replace("¡", "")
        clean_text = "".join(c for c in clean_text if c.isalnum() or c in [' ', '-', '_', '/', '.'])

        if details:
            clean_details = details.replace("ó", "o").replace("á", "a").replace("é", "e").replace("í", "i").replace("ú", "u")
            clean_details = clean_details.replace("ñ", "n").replace("¿", "").replace("¡", "")
            clean_details = "".join(c for c in clean_details if c.isalnum() or c in [' ', '-', '_', '/', '.'])
            return f"{clean_text}<br/>{clean_details}"
        return clean_text

    def generate_diagram(self, json_data: Dict[str, Any]) -> str:
        """Genera código Mermaid desde JSON"""
        self.node_counter = 0
        self.nodes = {}
        self.edges = []

        # Mapping from dependency names to container identifiers
        envs = json_data.get('envs', [])
        host_map = {}
        if envs:
            for host in envs[0].get('hosts', []):
                if host['type'] == 'container':
                    # Map dependency name to identifier
                    dep_name = host['identifier'].split('_')[0].capitalize()
                    if dep_name == 'Nginx':
                        host_map['NGINX'] = host['identifier']
                    elif dep_name == 'Django':
                        host_map['Django'] = host['identifier']
                    elif dep_name == 'Postgres':
                        host_map['PostgreSQL'] = host['identifier']

        # Usuarios
        users_node = self._add_node("Users/Clients", "external")
        self.nodes[users_node]['style'] = "fill:#e1f5fe"

        # Dependencies as tech components
        dependencies = json_data.get('dependencies', [])
        tech_nodes = {}
        for dep in dependencies:
            container = host_map.get(dep['name'], '') if dep.get('nature') == 'Interna' else ''
            port = dep.get('port', '')
            if dep.get('nature') == 'Interna':
                label = self._format_node_label(
                    f"{dep['name']} {dep.get('type', '')}",
                    f"Container: {container}<br/>Port: {port}" if port else f"Container: {container}"
                )
                node_type = "tech"
            else:  # Externa
                label = self._format_node_label(
                    f"{dep['name']} Server",
                    f"External {dep.get('type', '')}<br/>Port: {port}"
                )
                node_type = "dependency"
            node = self._add_node(label, node_type)
            if node_type == "dependency":
                self.nodes[node]['style'] = "fill:#ffebee"
            tech_nodes[dep['name']] = node

        # Health API
        if json_data.get('health_api'):
            health_node = self._add_node(
                self._format_node_label("Health API", "Endpoint: /api/health/"),
                "api"
            )
            tech_nodes['Health'] = health_node

        # Logs with specific names
        logs = json_data.get('logs', [])
        if logs:
            log_names = [log['name'] for log in logs]
            logs_label = self._format_node_label("Log Files", "<br/>".join(log_names))
            logs_node = self._add_node(logs_label, "logs")
            centralized_node = self._add_node(
                self._format_node_label("Centralized Logging",
                    "Elastic Stack" if json_data.get('centralized_logs') == 'Sí' else ""),
                "logging"
            )
            self._add_edge(logs_node, centralized_node)
            self.nodes[centralized_node]['style'] = "fill:#b2dfdb"
            tech_nodes['Logs'] = logs_node

        # Volumes
        volumes = json_data.get('volumes', [])
        if volumes:
            for vol in volumes:
                vol_label = self._format_node_label(f"Volume: {vol['name']}", f"Path: {vol['path']}<br/>Type: {vol['type']}")
                vol_node = self._add_node(vol_label, "volume")
                self.nodes[vol_node]['style'] = "fill:#d7ccc8"
                tech_nodes[f"Volume_{vol['name']}"] = vol_node
                # Connect to relevant services based on type
                if vol['type'] == 'static' or vol['type'] == 'media':
                    if 'NGINX' in tech_nodes:
                        self._add_edge(tech_nodes[f"Volume_{vol['name']}"], tech_nodes['NGINX'])
                    if 'Django' in tech_nodes:
                        self._add_edge(tech_nodes[f"Volume_{vol['name']}"], tech_nodes['Django'])
                elif vol['type'] == 'data':
                    if 'PostgreSQL' in tech_nodes:
                        self._add_edge(tech_nodes[f"Volume_{vol['name']}"], tech_nodes['PostgreSQL'])

        # Health Checks
        health_checks = json_data.get('health_checks', [])
        if health_checks:
            for hc in health_checks:
                hc_label = self._format_node_label(f"Health Check: {hc['service']}", f"Type: {hc['type']}<br/>Command: {hc['command']}")
                hc_node = self._add_node(hc_label, "health")
                self.nodes[hc_node]['style'] = "fill:#e8f5e8"
                tech_nodes[f"Health_{hc['service']}"] = hc_node
                # Connect to the service
                if hc['service'] in [t.lower() for t in tech_nodes.keys()]:
                    for key, node in tech_nodes.items():
                        if key.lower() == hc['service']:
                            self._add_edge(hc_node, node)

        # Connections
        if 'NGINX' in tech_nodes and 'Django' in tech_nodes:
            self._add_edge(users_node, tech_nodes['NGINX'])
            self._add_edge(tech_nodes['NGINX'], tech_nodes['Django'])
        if 'Django' in tech_nodes and 'PostgreSQL' in tech_nodes:
            self._add_edge(tech_nodes['Django'], tech_nodes['PostgreSQL'])
        if 'Health' in tech_nodes and 'Django' in tech_nodes:
            self._add_edge(tech_nodes['Health'], tech_nodes['Django'])
        if 'LDAP' in tech_nodes and 'Django' in tech_nodes:
            self._add_edge(tech_nodes['LDAP'], tech_nodes['Django'])

        # Generar código Mermaid
        mermaid_code = "graph TD\n"

        # Nodos
        for node_id, node_data in self.nodes.items():
            label = node_data['label']
            # Escape quotes and special characters in labels
            escaped_label = label.replace('"', '\\"').replace('\n', '<br/>')
            mermaid_code += f'    {node_id}["{escaped_label}"]\n'

        # Subgraph for main components
        main_components = [tech_nodes.get(t) for t in ['NGINX', 'Django', 'PostgreSQL', 'Health', 'Logs'] if t in tech_nodes]
        volume_components = [tech_nodes.get(f"Volume_{vol['name']}") for vol in volumes if f"Volume_{vol['name']}" in tech_nodes]
        health_components = [tech_nodes.get(f"Health_{hc['service']}") for hc in health_checks if f"Health_{hc['service']}" in tech_nodes]
        all_components = main_components + volume_components + health_components
        if all_components:
            mermaid_code += "\n    subgraph main_app [Gestión de formación]\n"
            for node in all_components:
                mermaid_code += f"        {node}\n"
            mermaid_code += "    end\n"

        # Conexiones
        mermaid_code += "\n"
        for from_node, to_node in self.edges:
            mermaid_code += f"    {from_node} --> {to_node}\n"

        # Estilos
        mermaid_code += "\n"
        for node_id, node_data in self.nodes.items():
            if 'style' in node_data:
                mermaid_code += f'    style {node_id} {node_data["style"]}\n'

        return mermaid_code

    def generate_html_preview(self, json_data: Dict[str, Any]) -> str:
        """Genera HTML completo con diagrama embebido"""
        mermaid_code = self.generate_diagram(json_data)

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diagrama de Arquitectura: {json_data.get('identification', {}).get('service_name', 'Servicio')}</title>
    <script type="module">
        import mermaid from 'https://cdn.skypack.dev/mermaid@10.6.1';
        mermaid.initialize({{
            startOnLoad: true,
            theme: 'default',
            securityLevel: 'loose'
        }});
    </script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .mermaid {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
        }}
        pre {{
            background: #f8f8f8;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Diagrama de Arquitectura: {json_data.get('identification', {}).get('service_name', 'Servicio')}</h1>

        <h2>Configuración JSON</h2>
        <pre>{json.dumps(json_data, indent=2, ensure_ascii=False)}</pre>

        <h2>Diagrama de Arquitectura</h2>
        <div class="mermaid">
{mermaid_code}
        </div>

        <h2>Componentes Detectados</h2>
        <ul>
"""

        # Añadir lista de componentes
        for node_id, node_data in self.nodes.items():
            html += f'            <li><strong>{node_id}</strong>: {node_data["label"]} ({node_data["type"]})</li>\n'

        html += """        </ul>
    </div>
</body>
</html>"""

        return html


def generate_diagram_from_json(json_file: str, output_format: str = "mermaid") -> str:
    """Función principal para generar diagrama desde archivo JSON"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        generator = ArchitectureDiagramGenerator()

        if output_format.lower() == "html":
            return generator.generate_html_preview(data)
        else:
            return generator.generate_diagram(data)

    except FileNotFoundError:
        return f"Error: No se encontró el archivo JSON: {json_file}"
    except json.JSONDecodeError as e:
        return f"Error: Error de formato JSON: {e}"
    except Exception as e:
        return f"Error inesperado: {e}"


if __name__ == "__main__":
    if len(sys.argv) != 2 and len(sys.argv) != 3:
        print("Uso: python diagram_generator.py <archivo.json> [html|mermaid]")
        print("Ejemplo: python diagram_generator.py config.json html")
        sys.exit(1)

    json_file = sys.argv[1]
    output_format = sys.argv[2] if len(sys.argv) == 3 else "mermaid"

    result = generate_diagram_from_json(json_file, output_format)

    if output_format.lower() == "html":
        output_file = json_file.replace('.json', '_diagram.html')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Diagrama HTML generado: {output_file}")
    else:
        print("Código Mermaid generado:")
        print(result)