---
title: "Architecture Diagram: Gestión de Formación"
author: "Code Supernova"
date: "2025-10-23"
---

# Architecture Diagram: Gestión de Formación

Based on the JSON configuration, here's the system architecture diagram:

> **Note**: To view the Mermaid diagram, ensure your Markdown viewer supports Mermaid rendering. In VS Code, install the "Markdown Preview Mermaid Support" extension or use an online Mermaid editor.

```mermaid
graph TD
    A["Users/Clients"]
    B["Django Application<br/>Container: django_app<br/>Port: 8000"]
    C["Nginx Proxy<br/>Container: nginx_proxy<br/>Port: 8082:80"]
    D["PostgreSQL Database<br/>Container: postgres_db<br/>Port: 5432"]
    E["LDAP Server<br/>External Autenticación<br/>Port: 389"]
    F["Health API<br/>Endpoint: /api/health/"]
    G["Log Files<br/>formacion.log<br/>security.log<br/>business.log<br/>anomaly.log<br/>performance.log<br/>formacion.json"]
    H["Centralized Logging<br/>Elastic Stack"]
    I["Volume: formacion_static_volume<br/>Path: /vol/web/staticfiles<br/>Type: static"]
    J["Volume: formacion_media_volume<br/>Path: /vol/web/media<br/>Type: media"]
    K["Volume: formacion_postgres_data<br/>Path: /var/lib/postgresql/data<br/>Type: data"]
    L["Health Check: postgres_db<br/>Type: command<br/>Command: pg_isready -U $$POSTGRES_USER -d postgres"]
    M["Health Check: django_app<br/>Type: http<br/>Command: /api/health/"]

    subgraph main_app [Gestión de formación]
        C
        B
        D
        F
        G
        I
        J
        K
        L
        M
    end

    G --> H
    I --> C
    I --> B
    J --> C
    J --> B
    K --> D
    A --> C
    C --> B
    B --> D
    F --> B
    E --> B

    style A fill:#e1f5fe
    style E fill:#ffebee
    style H fill:#b2dfdb
    style I fill:#d7ccc8
    style J fill:#d7ccc8
    style K fill:#d7ccc8
    style L fill:#e8f5e8
    style M fill:#e8f5e8
```

## Architecture Overview

### Main Components
- **Nginx Proxy**: Acts as a reverse proxy and load balancer, port 8082:80
- **Django Application**: Core business logic, port 8000
- **PostgreSQL Database**: Primary data storage, port 5432
- **LDAP Server**: External authentication service, port 389

### Dependencies
- **LDAP (Authentication)**: External dependency for user authentication
- **PostgreSQL (Database)**: Internal critical dependency for data persistence
- **Django (Backend)**: Self-dependency for the application itself

### Storage and Volumes
- **Volumes**: Persistent storage for static files, media, and database data
  - formacion_static_volume: /vol/web/staticfiles (static files)
  - formacion_media_volume: /vol/web/media (user media)
  - formacion_postgres_data: /var/lib/postgresql/data (database data)

### Health Checks and Monitoring
- **Health Checks**: Automated checks for service availability
  - PostgreSQL: Command-based check (pg_isready)
  - Django: HTTP-based check (/api/health/)
- **Health API**: Provides system health status via HTTP endpoint
- **Centralized Logging**: All logs are sent to Elastic Stack for analysis and retention

### Networking
- **Ports**: 8082:80 (Nginx), 8000:8000 (Django), 5432:5432 (PostgreSQL)
- **Configuration**: Hostname set to gesform.local

### Environment
- **EXP (Production)**: Single production environment with Docker Compose orchestration
- **Hosts**: Three main containers (nginx_proxy, django_app, postgres_db) running on xwiki.contactel.es

### System Boundary
The main application system "Gestión de formación" is grouped in a bounded box, containing:
- **Nginx Proxy** - entry point
- **Django Application** - core business logic
- **PostgreSQL Database** - data storage
- **Health API** - health check endpoint
- **Log Files** - application logs
- **Volumes** - persistent storage
- **Health Checks** - monitoring checks

### Data Flow
1. Users access the system through Nginx
2. Nginx forwards requests to Django application
3. Django interacts with PostgreSQL for data and LDAP for authentication
4. Health API provides system status
5. Logs are centralized for analysis
6. Volumes ensure persistent storage for files and data

This architecture represents the "Gestión de formación" system as defined in the JSON configuration, showing the main application components, dependencies, storage, monitoring, and logging infrastructure for comprehensive automated monitoring.