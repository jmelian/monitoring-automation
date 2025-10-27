# Generador de Diagramas de Arquitectura

Este sistema permite generar diagramas de arquitectura automáticamente desde configuraciones JSON de monitorización.

## Funcionalidades

### 1. Integración en el Formulario Web
El formulario `formulario_monitorización.html` ahora incluye:
- **Vista previa en tiempo real**: El diagrama se actualiza automáticamente mientras se completa el formulario
- **Generación automática**: Al generar el JSON, se crea el diagrama de arquitectura correspondiente
- **Validación visual**: Permite verificar gráficamente la configuración antes de procesarla

### 2. Script Independiente
El script `diagram_generator.py` permite generar diagramas desde cualquier archivo JSON:

```bash
# Generar código Mermaid
python diagram_generator.py config.json

# Generar HTML completo con diagrama
python diagram_generator.py config.json html
```

## Componentes Detectados Automáticamente

El generador analiza el JSON y crea nodos para:

### Componentes Principales
- **Servicio principal**: Sistema central con boundary box
- **Tech stack**: Tecnologías y versiones
- **Dependencies**: Dependencias internas/externas con tipos
- **Health API**: Endpoints de health checks
- **Logs**: Archivos de log y centralización
- **Environments**: Entornos de despliegue

### Conexiones Automáticas
- Usuarios → Sistema principal
- Sistema → Tecnologías del stack
- Sistema → Dependencias
- Health API → Sistema
- Logs → Centralized Logging
- Environments → Sistema

## Ejemplo de Uso

### Desde el formulario web:
1. Complete el formulario de monitorización
2. Observe cómo el diagrama se actualiza en tiempo real
3. Genere el JSON para ver el diagrama final

### Desde línea de comandos:
```bash
# Con el JSON de ejemplo
python diagram_generator.py gesform.json html
# Genera: gesform_diagram.html

# Con cualquier JSON de configuración
python diagram_generator.py mi_config.json
# Muestra código Mermaid en consola
```

## Archivos Generados

- `architecture_diagram.html`: Diagrama del JSON de ejemplo
- `architecture_diagram.md`: Documentación del diagrama
- `diagram_generator.py`: Script generador independiente
- `gesform_diagram.html`: Diagrama generado desde gesform.json

## Ventajas

1. **Validación visual**: Verificar la arquitectura antes de implementar
2. **Documentación automática**: Diagramas siempre actualizados
3. **Consistencia**: Mismo formato para todos los servicios
4. **Flexibilidad**: Funciona con cualquier configuración JSON válida
5. **Tiempo real**: Preview durante la configuración

## Formato de Diagrama

Los diagramas se generan en formato Mermaid con:
- Colores diferenciados por tipo de componente
- Boundary box para el sistema principal
- Conexiones basadas en las relaciones del JSON
- Estilos consistentes y profesionales

Este sistema mejora significativamente el proceso de configuración de monitorización al proporcionar validación visual inmediata y documentación automática de la arquitectura.