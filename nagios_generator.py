#!/usr/bin/env python3
"""
Nagios Configuration Generator
Genera configuraciones de Nagios basadas en el JSON del formulario de monitorización
"""

import json
import os
from datetime import datetime
from jinja2 import Template


class NagiosConfigGenerator:
    """Genera configuraciones completas de Nagios desde JSON"""

    def __init__(self, json_data, output_dir="output/nagios"):
        self.data = json_data
        self.output_dir = output_dir
        self.templates_dir = "templates/nagios"

        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)

        # Mapear prioridades a check intervals y severidad
        self.priority_mapping = {
            "Crítica": {"interval": 60, "retry": 2, "max_attempts": 3},
            "Alta": {"interval": 300, "retry": 3, "max_attempts": 4},
            "Media": {"interval": 600, "retry": 5, "max_attempts": 5},
            "Baja": {"interval": 1800, "retry": 10, "max_attempts": 10}
        }

        # Mapear protocolos a comandos de Nagios
        self.protocol_commands = {
            "http": "check_http",
            "tcp": "check_tcp",
            "icmp": "check_ping",
            "dns": "check_dns",
            "ldap": "check_ldap",
            "smtp": "check_smtp",
            "sql": "check_mysql"
        }

    def _get_priority_config(self, priority):
        """Obtiene configuración de check basada en prioridad"""
        return self.priority_mapping.get(priority, self.priority_mapping["Media"])

    def _generate_host_id(self, env_name, host_type, host_id):
        """Genera ID único para host"""
        return f"host_{env_name.lower()}_{host_id.replace('.', '_').replace('-', '_')}"

    def _generate_service_id(self, service_name, dep_name, env_name):
        """Genera ID único para servicio"""
        return f"svc_{service_name.lower().replace(' ', '_')}_{dep_name.lower().replace(' ', '_')}_{env_name.lower()}"

    def generate_hosts_config(self):
        """Genera configuración de hosts basada en entornos"""
        hosts_config = []
        hosts_data = []

        for env in self.data.get("envs", []):
            env_name = env.get("name", "unknown")
            env_desc = env.get("desc", "")

            for host in env.get("hosts", []):
                host_id = self._generate_host_id(env_name, host.get("type", "host"), host.get("identifier", ""))
                host_address = host.get("identifier", "")

                # Determinar dirección basada en tipo de host
                if host.get("type") == "container":
                    # Para contenedores, usar nombre del contenedor como alias
                    host_alias = f"{env_name} - {host.get('identifier', '')}"
                elif host.get("type") == "domain":
                    host_address = host.get("identifier", "")
                    host_alias = f"{env_name} - {host_address}"
                else:
                    host_alias = f"{env_name} - {host_address}"

                host_config = {
                    "host_id": host_id,
                    "host_name": host_id,
                    "alias": host_alias,
                    "address": host_address,
                    "env_name": env_name,
                    "env_desc": env_desc,
                    "host_type": host.get("type", "host"),
                    "check_interval": 300,
                    "retry_interval": 60,
                    "max_check_attempts": 3
                }

                hosts_data.append(host_config)

                # Template para configuración de host
                host_template = Template("""
define host {
    host_name                    {{ host_id }}
    alias                        {{ alias }}
    address                      {{ address }}
    check_period                 24x7
    check_interval               {{ check_interval }}
    retry_interval               {{ retry_interval }}
    max_check_attempts           {{ max_check_attempts }}
    check_command                check_host_alive
    notification_interval        60
    notification_period          24x7
    notifications_enabled        1
    register                     1
}
""")
                hosts_config.append(host_template.render(**host_config))

        return "\n".join(hosts_config), hosts_data

    def generate_contacts_config(self):
        """Genera configuración de contactos basada en responsables"""
        contacts_config = []
        contacts_data = []

        for resp in self.data.get("responsables", []):
            contact_id = f"contact_{resp.get('nombre', '').lower().replace(' ', '_')}"
            contact_name = resp.get("nombre", "")
            contact_email = resp.get("email", "")

            contact_config = {
                "contact_id": contact_id,
                "contact_name": contact_name,
                "email": contact_email,
                "service_notification_period": "24x7",
                "host_notification_period": "24x7",
                "service_notification_options": "w,u,c,r,f,s",
                "host_notification_options": "d,u,r,f,s",
                "service_notification_commands": "notify-service-by-email",
                "host_notification_commands": "notify-host-by-email"
            }

            contacts_data.append(contact_config)

            # Template para configuración de contacto
            contact_template = Template("""
define contact {
    contact_name                 {{ contact_name }}
    alias                        {{ contact_name }}
    email                        {{ email }}
    service_notification_period  {{ service_notification_period }}
    host_notification_period     {{ host_notification_period }}
    service_notification_options {{ service_notification_options }}
    host_notification_options    {{ host_notification_options }}
    service_notification_commands {{ service_notification_commands }}
    host_notification_commands   {{ host_notification_commands }}
    register                     1
}
""")
            contacts_config.append(contact_template.render(**contact_config))

        # Crear contactgroup para el servicio
        service_name = self.data.get("identification", {}).get("service_name", "unknown")
        contactgroup_id = f"cg_{service_name.lower().replace(' ', '_')}"

        contactgroup_template = Template("""
define contactgroup {
    contactgroup_name            {{ contactgroup_id }}
    alias                        {{ service_name }} Team
    members                      {% for contact in contacts_data %}{{ contact.contact_id }}{% if not loop.last %},{% endif %}{% endfor %}
    register                     1
}
""")

        contacts_config.append(contactgroup_template.render(
            contactgroup_id=contactgroup_id,
            service_name=service_name,
            contacts_data=contacts_data
        ))

        return "\n".join(contacts_config), contacts_data

    def generate_services_config(self):
        """Genera configuración de servicios basada en dependencias"""
        services_config = []
        services_data = []

        service_name = self.data.get("identification", {}).get("service_name", "unknown")
        priority = self.data.get("identification", {}).get("priority", "Media")
        priority_config = self._get_priority_config(priority)

        # Crear servicio para health API si existe
        if self.data.get("health_api"):
            health_details = self.data.get("health_api_details", {})
            for env in self.data.get("envs", []):
                env_name = env.get("name", "")

                service_id = f"svc_health_{service_name.lower().replace(' ', '_')}_{env_name.lower()}"

                service_config = {
                    "service_id": service_id,
                    "service_description": f"Health Check - {service_name}",
                    "host_name": "*",  # Aplicar a todos los hosts del servicio
                    "check_command": f"check_http -H {health_details.get('endpoint', '').replace('http://', '').replace('https://', '').split('/')[0]} -u {health_details.get('endpoint', '')}",
                    "check_interval": health_details.get("interval_sec", 300),
                    "retry_interval": 60,
                    "max_check_attempts": 3,
                    "notification_interval": 60,
                    "contact_groups": f"cg_{service_name.lower().replace(' ', '_')}"
                }

                services_data.append(service_config)

                service_template = Template("""
define service {
    service_description          {{ service_description }}
    host_name                    {{ host_name }}
    check_command                {{ check_command }}
    check_interval               {{ check_interval }}
    retry_interval               {{ retry_interval }}
    max_check_attempts           {{ max_check_attempts }}
    check_period                 24x7
    notification_interval        {{ notification_interval }}
    notification_period          24x7
    notifications_enabled        1
    contact_groups               {{ contact_groups }}
    register                     1
}
""")
                services_config.append(service_template.render(**service_config))

        # Crear servicios para cada dependencia
        for dep in self.data.get("dependencies", []):
            dep_name = dep.get("name", "")
            dep_port = dep.get("port", "")
            dep_protocol = dep.get("check_protocol", "tcp")
            dep_impact = dep.get("impact", "Media")

            # Saltar dependencias sin puerto o protocolo definido
            if not dep_port or not dep_protocol:
                continue

            impact_config = self._get_priority_config(dep_impact)

            for env in self.data.get("envs", []):
                env_name = env.get("name", "")

                # Crear servicio para cada host en el entorno
                for host in env.get("hosts", []):
                    host_id = self._generate_host_id(env_name, host.get("type", "host"), host.get("identifier", ""))

                    service_id = self._generate_service_id(service_name, dep_name, env_name)

                    # Determinar comando de check basado en protocolo
                    if dep_protocol == "http":
                        check_command = f"check_http -H {host.get('identifier', '')} -p {dep_port}"
                    elif dep_protocol == "tcp":
                        check_command = f"check_tcp -H {host.get('identifier', '')} -p {dep_port}"
                    elif dep_protocol == "icmp":
                        check_command = f"check_ping -H {host.get('identifier', '')}"
                    else:
                        check_command = f"check_tcp -H {host.get('identifier', '')} -p {dep_port}"

                    service_config = {
                        "service_id": service_id,
                        "service_description": f"{dep_name} ({dep_protocol.upper()})",
                        "host_name": host_id,
                        "check_command": check_command,
                        "check_interval": impact_config["interval"],
                        "retry_interval": impact_config["retry"],
                        "max_check_attempts": impact_config["max_attempts"],
                        "notification_interval": 60,
                        "contact_groups": f"cg_{service_name.lower().replace(' ', '_')}"
                    }

                    services_data.append(service_config)

                    service_template = Template("""
define service {
    service_description          {{ service_description }}
    host_name                    {{ host_name }}
    check_command                {{ check_command }}
    check_interval               {{ check_interval }}
    retry_interval               {{ retry_interval }}
    max_check_attempts           {{ max_check_attempts }}
    check_period                 24x7
    notification_interval        {{ notification_interval }}
    notification_period          24x7
    notifications_enabled        1
    contact_groups               {{ contact_groups }}
    register                     1
}
""")
                    services_config.append(service_template.render(**service_config))

        return "\n".join(services_config), services_data

    def generate_commands_config(self):
        """Genera configuración de comandos personalizados"""
        commands_config = []

        # Comandos estándar de Nagios
        standard_commands = """
# Comandos estándar de Nagios
define command {
    command_name    check_host_alive
    command_line    $USER1$/check_ping -H $HOSTADDRESS$ -w 3000.0,80% -c 5000.0,100% -p 5
}

define command {
    command_name    check_http
    command_line    $USER1$/check_http -H $ARG1$ -u $ARG2$
}

define command {
    command_name    check_tcp
    command_line    $USER1$/check_tcp -H $ARG1$ -p $ARG2$
}

define command {
    command_name    check_ping
    command_line    $USER1$/check_ping -H $ARG1$ -w 100.0,20% -c 500.0,60% -p 5
}

define command {
    command_name    check_dns
    command_line    $USER1$/check_dns -H $ARG1$
}

define command {
    command_name    check_ldap
    command_line    $USER1$/check_ldap -H $ARG1$ -p $ARG2$
}

define command {
    command_name    check_smtp
    command_line    $USER1$/check_smtp -H $ARG1$ -p $ARG2$
}

define command {
    command_name    check_mysql
    command_line    $USER1$/check_mysql -H $ARG1$ -P $ARG2$ -u $ARG3$ -p $ARG4$
}

define command {
    command_name    notify-host-by-email
    command_line    /usr/bin/printf "%b" "***** Nagios *****\n\nNotification Type: $NOTIFICATIONTYPE$\nHost: $HOSTNAME$\nState: $HOSTSTATE$\nAddress: $HOSTADDRESS$\nInfo: $HOSTOUTPUT$\n\nDate/Time: $LONGDATETIME$\n" | /usr/bin/mail -s "** $NOTIFICATIONTYPE$ Host Alert: $HOSTNAME$ is $HOSTSTATE$ **" $CONTACTEMAIL$
}

define command {
    command_name    notify-service-by-email
    command_line    /usr/bin/printf "%b" "***** Nagios *****\n\nNotification Type: $NOTIFICATIONTYPE$\nService: $SERVICEDESC$\nHost: $HOSTALIAS$\nAddress: $HOSTADDRESS$\nState: $SERVICESTATE$\n\nDate/Time: $LONGDATETIME$\n\nAdditional Info:\n\n$SERVICEOUTPUT$\n" | /usr/bin/mail -s "** $NOTIFICATIONTYPE$ Service Alert: $HOSTALIAS$/$SERVICEDESC$ is $SERVICESTATE$ **" $CONTACTEMAIL$
}
"""

        commands_config.append(standard_commands)
        return "\n".join(commands_config)

    def generate_all_configs(self):
        """Genera todas las configuraciones de Nagios"""
        print("Generando configuraciones de Nagios...")

        # Generar cada tipo de configuración
        hosts_cfg, hosts_data = self.generate_hosts_config()
        contacts_cfg, contacts_data = self.generate_contacts_config()
        services_cfg, services_data = self.generate_services_config()
        commands_cfg = self.generate_commands_config()

        # Crear configuración principal de Nagios
        main_cfg = f"""
# Configuración de Nagios generada automáticamente
# Servicio: {self.data.get('identification', {}).get('service_name', 'Unknown')}
# Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Archivo generado por el sistema de automatización de monitorización

# Configuración principal
cfg_dir=/etc/nagios/conf.d

# Incluir configuraciones generadas
cfg_file=/etc/nagios/objects/hosts.cfg
cfg_file=/etc/nagios/objects/services.cfg
cfg_file=/etc/nagios/objects/contacts.cfg
cfg_file=/etc/nagios/objects/commands.cfg
"""

        # Guardar archivos individuales
        files_to_save = [
            ("hosts.cfg", hosts_cfg),
            ("services.cfg", services_cfg),
            ("contacts.cfg", contacts_cfg),
            ("commands.cfg", commands_cfg),
            ("nagios.cfg", main_cfg)
        ]

        saved_files = []
        for filename, content in files_to_save:
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            saved_files.append(filepath)
            print(f"✓ Archivo generado: {filepath}")

        return saved_files, {
            "hosts": hosts_data,
            "contacts": contacts_data,
            "services": services_data
        }


def generate_nagios_from_json(json_file, output_dir="output/nagios"):
    """Función principal para generar configuración de Nagios desde JSON"""
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        generator = NagiosConfigGenerator(data, output_dir)
        files, metadata = generator.generate_all_configs()

        print(f"\n✓ Configuración de Nagios generada exitosamente!")
        print(f"✓ Archivos generados: {len(files)}")
        print(f"✓ Hosts configurados: {len(metadata['hosts'])}")
        print(f"✓ Servicios configurados: {len(metadata['services'])}")
        print(f"✓ Contactos configurados: {len(metadata['contacts'])}")

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
        print("Uso: python nagios_generator.py <archivo.json>")
        sys.exit(1)

    json_file = sys.argv[1]
    generate_nagios_from_json(json_file)