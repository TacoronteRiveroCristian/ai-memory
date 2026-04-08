"""Benchmark catalog: 15 projects (8 energy + 7 software) with ~20-25 memories each."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


BENCHMARK_TEST_NOW = "2030-01-01T00:00:00+00:00"

SHARED_METHOD_QUERY = (
    "condition monitoring quality control de series temporales anomaly detection "
    "telemetría operacional industrial"
)

# ── Shared tag constants ────────────────────────────────────────────

ENERGY_TAGS = {
    "method_condition": "method/condition-monitoring",
    "method_quality": "method/time-series-quality-control",
    "method_anomaly": "method/anomaly-detection",
    "stack_pipeline": "stack/telemetry-pipeline",
    "protocol_modbus": "protocol/modbus",
    "protocol_iec104": "protocol/iec-104",
    "metric_availability": "metric/availability",
    "metric_power_quality": "metric/power-quality",
}

SOFTWARE_TAGS = {
    "pattern_rest": "pattern/rest-api",
    "pattern_event_driven": "pattern/event-driven",
    "pattern_cqrs": "pattern/cqrs",
    "stack_docker": "stack/docker",
    "stack_k8s": "stack/kubernetes",
    "stack_ci": "stack/ci-cd",
    "concern_auth": "concern/auth",
    "concern_observability": "concern/observability",
    "concern_testing": "concern/testing",
    "concern_data_quality": "concern/data-quality",
}

# ── Common content prefixes ─────────────────────────────────────────

COMMON_METHOD_PREFIX = (
    "Metodología común de monitorización industrial basada en condition monitoring, "
    "quality control de series temporales y anomaly detection sobre telemetría operacional."
)
COMMON_PIPELINE_PREFIX = (
    "Pipeline común de telemetría industrial con gateway edge, normalización de protocolos, "
    "timestamp unificado y control de calidad antes del historiado."
)
COMMON_SW_METHOD_PREFIX = (
    "Shared software methodology based on domain-driven design, event sourcing where "
    "appropriate, and observability-first instrumentation across all services."
)
COMMON_SW_PIPELINE_PREFIX = (
    "Shared CI/CD pipeline using GitHub Actions with lint, test, build, deploy stages, "
    "container-based builds, and automated rollback on health-check failure."
)

# ═══════════════════════════════════════════════════════════════════
# ENERGY PROJECTS (8)
# ═══════════════════════════════════════════════════════════════════

_E1_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.98,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["metric_availability"], "domain/ems", "asset/fotovoltaica"],
        "content": f"{COMMON_METHOD_PREFIX} En el EMS fotovoltaico esta metodología se usa para correlacionar irradiancia, consignas del PPC, clipping, alarmas por bloque y disponibilidad por inversor.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.94,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["protocol_iec104"], ENERGY_TAGS["metric_power_quality"], "domain/ems", "asset/fotovoltaica", "stack/ppc"],
        "content": f"{COMMON_PIPELINE_PREFIX} En la planta fotovoltaica el pipeline EMS unifica telemetría de inversores, PPC, contador fiscal y estación meteo para controlar rampas, cos phi y curtailment.",
    },
    {
        "key": "ppc-weather-correlation",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_quality"], ENERGY_TAGS["metric_power_quality"], "domain/ems", "domain/meteorologia", "stack/ppc"],
        "content": "El EMS fotovoltaico cruza irradiancia, temperatura de módulo y consignas del PPC para explicar clipping, ramp-rate events y recortes preventivos por calidad de red.",
    },
    {
        "key": "availability-kpis",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], ENERGY_TAGS["method_anomaly"], "domain/ems", "asset/inversores"],
        "content": "Los KPI de disponibilidad del EMS separan indisponibilidad por inversor, tracker, SCB y comunicaciones para priorizar incidencias con mayor impacto energético.",
    },
    {
        "key": "inverter-block-alarms",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ems", "asset/inversores", "asset/fotovoltaica"],
        "content": "Las alarmas por bloque de inversores se agrupan por string-combiner-box y se correlacionan con irradiancia y temperatura para distinguir sombras de fallos reales.",
    },
    {
        "key": "curtailment-events",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/ems", "stack/ppc", "asset/fotovoltaica"],
        "content": "Los eventos de curtailment del EMS se clasifican en mandados por operador, por ramp-rate y por calidad de red, registrando energía perdida estimada por cada tipo.",
    },
    {
        "key": "scb-monitoring",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/ems", "asset/fotovoltaica"],
        "content": "La monitorización de string combiner boxes compara corrientes por string para detectar diodos bypass activos, strings abiertos y degradación gradual de módulos.",
    },
    {
        "key": "cos-phi-regulation",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["protocol_modbus"], "domain/ems", "stack/ppc"],
        "content": "La regulación de cos phi del EMS combina consignas del PPC con medidas del analizador de red para mantener factor de potencia dentro de la banda de compliance.",
    },
    {
        "key": "ramp-rate-control",
        "memory_type": "architecture",
        "importance": 0.90,
        "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["method_quality"], "domain/ems", "stack/ppc", "asset/fotovoltaica"],
        "content": "El control de rampas del EMS limita la variación de potencia activa en ventanas de 1 y 10 minutos según código de red, usando BESS si está disponible como buffer.",
    },
    {
        "key": "tracker-alignment",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ems", "asset/fotovoltaica", "asset/trackers"],
        "content": "El EMS valida alineamiento de trackers comparando producción entre filas adyacentes y detectando backtracking incorrecto en horas de bajo ángulo solar.",
    },
    {
        "key": "energy-balance",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/ems", "asset/fotovoltaica", "metric/energy-yield"],
        "content": "El balance energético diario cierra producción bruta, auxiliares, pérdidas por disponibilidad, curtailment y transformador para conciliar con el contador fiscal.",
    },
    {
        "key": "ppc-setpoint-history",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/ems", "stack/ppc"],
        "content": "El historial de consignas del PPC se almacena con timestamp, fuente (operador, automático, remoto) y potencia asociada para trazabilidad regulatoria.",
    },
    {
        "key": "communication-redundancy",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["protocol_iec104"], "domain/ems"],
        "content": "El EMS mantiene dos rutas de comunicación (Modbus TCP primario, IEC-104 backup) con conmutación automática y registro de latencia por canal.",
    },
    {
        "key": "meteo-integration",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_quality"], "domain/ems", "domain/meteorologia"],
        "content": "La integración meteorológica del EMS recibe GHI, DHI, temperatura ambiente y velocidad de viento para alimentar modelos de producción esperada y detección de anomalías.",
    },
    {
        "key": "soiling-detection",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/ems", "asset/fotovoltaica"],
        "content": "La detección de soiling compara ratio de rendimiento entre módulos limpios de referencia y el resto del campo para estimar pérdidas y programar limpieza.",
    },
    {
        "key": "grid-code-compliance",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/ems", "stack/ppc", "regulation/grid-code"],
        "content": "El cumplimiento de código de red se monitoriza en tiempo real con alertas por violación de rampa, factor de potencia fuera de banda y tensión fuera de rango.",
    },
    {
        "key": "data-historian",
        "memory_type": "architecture",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/ems", "stack/historian"],
        "content": "El historiador del EMS almacena series a 1s para diagnóstico y a 1min para operación, con compresión swinging-door y retención configurable por tipo de señal.",
    },
    {
        "key": "alarm-management",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ems", "asset/fotovoltaica"],
        "content": "La gestión de alarmas del EMS aplica shelving temporal, agrupación por zona y priorización por impacto energético para evitar saturación del operador.",
    },
    {
        "key": "performance-ratio",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["metric_availability"], ENERGY_TAGS["method_quality"], "domain/ems", "metric/performance-ratio"],
        "content": "El performance ratio se calcula por inversor, bloque y planta con correcciones por temperatura, clipping y curtailment para aislar pérdidas técnicas de operativas.",
    },
    {
        "key": "night-monitoring",
        "memory_type": "general",
        "importance": 0.78,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/ems", "asset/fotovoltaica"],
        "content": "La monitorización nocturna detecta consumos parásitos, fallos de aislamiento y corrientes inversas en inversores que no deberían tener actividad fuera de horas solares.",
    },
]

_E2_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.98,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], "domain/meteorologia", "asset/estaciones-meteo", ENERGY_TAGS["metric_availability"]],
        "content": f"{COMMON_METHOD_PREFIX} En la monitorización de estaciones meteorológicas se usa para validar irradiancia, temperatura ambiente, viento, humedad y drift de sensores antes de publicar KPI operativos.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["metric_availability"], "domain/meteorologia", "asset/estaciones-meteo"],
        "content": f"{COMMON_PIPELINE_PREFIX} En las estaciones meteorológicas el pipeline integra dataloggers, gateways Modbus y reglas de QA/QC para irradiancia, temperatura y viento antes de exponer series limpias al resto de sistemas.",
    },
    {
        "key": "sensor-drift-correlation",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], "domain/meteorologia", "asset/estaciones-meteo", "metric/irradiance-quality"],
        "content": "La correlación entre piranómetro, célula de referencia y satélite permite detectar drift, sombras parciales y suciedad persistente en estaciones meteo.",
    },
    {
        "key": "gateway-availability",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["metric_availability"], ENERGY_TAGS["protocol_modbus"], "domain/meteorologia", "stack/gateway-edge"],
        "content": "La disponibilidad de la estación meteorológica se calcula separando fallos de sensor, pérdida de gateway, latencia satelital y huecos por mantenimiento.",
    },
    {
        "key": "irradiance-qc-rules",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_quality"], "domain/meteorologia", "metric/irradiance-quality"],
        "content": "Las reglas QA/QC de irradiancia aplican test de límites físicos, consistencia entre GHI/DHI/DNI y comparación con modelo de cielo claro para marcar datos sospechosos.",
    },
    {
        "key": "wind-measurement",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_quality"], "domain/meteorologia", "asset/estaciones-meteo", "metric/wind-speed"],
        "content": "La medición de viento valida anemómetro de copas y sónico cruzando dirección, ráfaga y media para detectar bloqueo mecánico o calentador atascado.",
    },
    {
        "key": "temperature-validation",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_quality"], "domain/meteorologia", "metric/temperature"],
        "content": "La validación de temperatura ambiente compara PT100 con termómetro de respaldo y aplica test de persistencia y salto para detectar sensor desconectado.",
    },
    {
        "key": "satellite-crosscheck",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], "domain/meteorologia", "source/satellite"],
        "content": "La referencia satelital se usa como tercera fuente independiente para irradiancia, permitiendo detectar drift lento que no saltan los test punto a punto.",
    },
    {
        "key": "datalogger-config",
        "memory_type": "architecture",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], "domain/meteorologia", "asset/datalogger"],
        "content": "Los dataloggers se configuran para muestreo a 1s y envío de agregados a 1min, con buffer local de 7 días para recuperar huecos tras pérdida de comunicación.",
    },
    {
        "key": "humidity-precipitation",
        "memory_type": "general",
        "importance": 0.79,
        "tags": [ENERGY_TAGS["method_quality"], "domain/meteorologia", "metric/humidity"],
        "content": "La humedad relativa y la precipitación se usan para contextualizar eventos de soiling, corrosión y rendimiento de módulos fotovoltaicos bajo condiciones extremas.",
    },
    {
        "key": "calibration-tracking",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_condition"], "domain/meteorologia", "asset/estaciones-meteo"],
        "content": "El sistema registra fechas de calibración, factores de corrección y certificados de cada sensor para aplicar compensaciones retroactivas si se detecta drift.",
    },
    {
        "key": "multi-site-comparison",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/meteorologia", "asset/estaciones-meteo"],
        "content": "La comparación multi-sitio cruza estaciones vecinas para detectar anomalías localizadas como sombras de nueva construcción o cambios de albedo.",
    },
    {
        "key": "data-gap-recovery",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["metric_availability"], "domain/meteorologia"],
        "content": "La recuperación de huecos combina interpolación temporal, referencia satelital y estaciones vecinas, marcando siempre el origen del dato reconstruido.",
    },
    {
        "key": "alarm-thresholds",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [ENERGY_TAGS["method_condition"], "domain/meteorologia", "asset/estaciones-meteo"],
        "content": "Los umbrales de alarma se definen por sensor y por estación con bandas estacionales para evitar falsos positivos en invierno por baja irradiancia.",
    },
    {
        "key": "soiling-correlation",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/meteorologia", "domain/ems"],
        "content": "La correlación soiling-meteo usa precipitación, humedad y dirección de viento para predecir acumulación de polvo y programar lavados preventivos.",
    },
    {
        "key": "report-generation",
        "memory_type": "general",
        "importance": 0.78,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/meteorologia"],
        "content": "Los informes meteorológicos mensuales incluyen disponibilidad por sensor, completitud de datos, eventos de QA/QC y comparación con normales climatológicas.",
    },
    {
        "key": "edge-computing",
        "memory_type": "architecture",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/meteorologia", "stack/gateway-edge"],
        "content": "El edge computing ejecuta reglas de QA/QC básicas en el gateway para marcar datos sospechosos antes de transmitir, reduciendo ancho de banda y latencia.",
    },
    {
        "key": "api-exposure",
        "memory_type": "architecture",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/meteorologia"],
        "content": "La API REST de meteorología expone series limpias con metadatos de calidad, permitiendo a EMS, SCADA y mantenimiento consumir datos validados sin duplicar lógica.",
    },
]

_E3_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], "domain/scada", "asset/bess", ENERGY_TAGS["metric_availability"]],
        "content": f"{COMMON_METHOD_PREFIX} En el SCADA híbrido solar+BESS esta metodología se usa para coordinar SoC, consignas de despacho, alarmas de potencia y disponibilidad de convertidores de batería e inversores solares.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["protocol_iec104"], "domain/scada", "asset/bess", "asset/fotovoltaica"],
        "content": f"{COMMON_PIPELINE_PREFIX} En el SCADA híbrido se unifica telemetría de BESS, inversores solares y medidores de red para explicar rampas, SoC útil y eventos de limitación operativa.",
    },
    {
        "key": "dispatch-ramp-control",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["method_anomaly"], "domain/scada", "asset/bess", "stack/dispatch"],
        "content": "El control híbrido prioriza ramp-rate compliance y estado de carga estable antes de perseguir consignas agresivas del mercado o del despacho centralizado.",
    },
    {
        "key": "bess-availability-kpis",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/scada", "asset/bess", "asset/inversores"],
        "content": "La disponibilidad híbrida separa indisponibilidad del BESS, limitación del PCS y bloqueos del SCADA para no atribuir toda la pérdida al activo solar.",
    },
    {
        "key": "soc-management",
        "memory_type": "general",
        "importance": 0.90,
        "tags": [ENERGY_TAGS["method_condition"], "domain/scada", "asset/bess"],
        "content": "La gestión de SoC define bandas operativas (20-80%) con zonas de reserva para regulación primaria y protección contra sobrecarga y descarga profunda.",
    },
    {
        "key": "pcs-thermal-management",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/scada", "asset/bess"],
        "content": "El PCS del BESS reduce potencia automáticamente cuando la temperatura de celda supera umbrales, priorizando vida útil sobre producción inmediata.",
    },
    {
        "key": "hybrid-dispatch-modes",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": ["domain/scada", "asset/bess", "asset/fotovoltaica", "stack/dispatch"],
        "content": "El SCADA híbrido soporta modos de despacho: peak-shaving, rampa-solar, arbitraje y regulación frecuencia, con prioridad configurable por horario y precio.",
    },
    {
        "key": "grid-interaction",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["protocol_iec104"], "domain/scada"],
        "content": "La interacción con red via IEC-104 permite al operador enviar consignas remotas de potencia activa y reactiva que el SCADA ejecuta respetando límites físicos.",
    },
    {
        "key": "degradation-tracking",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_condition"], "domain/scada", "asset/bess"],
        "content": "El seguimiento de degradación del BESS compara capacidad nominal vs real mediante ciclos de carga/descarga controlados para estimar vida útil residual.",
    },
    {
        "key": "protection-coordination",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["method_condition"], "domain/scada", "asset/bess", "asset/fotovoltaica"],
        "content": "La coordinación de protecciones del híbrido asegura que disparo de BESS no provoque transitorio en solar y viceversa, con secuencias de reconexión controladas.",
    },
    {
        "key": "frequency-regulation",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/scada", "asset/bess"],
        "content": "El BESS aporta regulación primaria de frecuencia con tiempo de respuesta sub-segundo, inyectando o absorbiendo potencia según desviación respecto a 50Hz.",
    },
    {
        "key": "market-integration",
        "memory_type": "general",
        "importance": 0.82,
        "tags": ["domain/scada", "asset/bess", "stack/dispatch"],
        "content": "La integración con mercado recibe precios horarios y programa ciclos de carga/descarga del BESS para maximizar ingresos respetando restricciones de red.",
    },
    {
        "key": "event-sequence-recording",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/scada", "asset/bess"],
        "content": "El SCADA registra secuencia de eventos (SOE) con resolución de 1ms para análisis post-mortem de incidentes, ordenando causas y consecuencias.",
    },
    {
        "key": "auxiliary-consumption",
        "memory_type": "general",
        "importance": 0.79,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/scada", "asset/bess"],
        "content": "El consumo auxiliar del BESS (HVAC, BMS, comunicaciones) se monitoriza para incluirlo en el balance energético y detectar anomalías de refrigeración.",
    },
    {
        "key": "firmware-management",
        "memory_type": "general",
        "importance": 0.78,
        "tags": [ENERGY_TAGS["method_condition"], "domain/scada", "asset/bess"],
        "content": "La gestión de firmware del PCS y BMS se coordina con ventanas de mantenimiento, manteniendo registro de versiones y rollback disponible.",
    },
    {
        "key": "safety-interlocks",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": [ENERGY_TAGS["method_condition"], "domain/scada", "asset/bess"],
        "content": "Los interlocks de seguridad del BESS inhiben operación por temperatura extrema, fuga de gas, apertura de puerta o pérdida de comunicación BMS.",
    },
    {
        "key": "black-start-capability",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/scada", "asset/bess", "asset/fotovoltaica"],
        "content": "La capacidad de black-start del híbrido permite arrancar la planta solar desde el BESS sin red externa, siguiendo secuencia de energización controlada.",
    },
    {
        "key": "communication-architecture",
        "memory_type": "architecture",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["protocol_iec104"], "domain/scada"],
        "content": "La arquitectura de comunicaciones del SCADA híbrido usa anillo Ethernet redundante entre PCS, inversores y RTU con failover automático inferior a 50ms.",
    },
]

_E4_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["stack_pipeline"], "domain/power-quality", "stack/ppc"],
        "content": f"{COMMON_METHOD_PREFIX} En calidad de red y PPC se usa para correlacionar huecos, THD, flicker, consignas de reactiva y disponibilidad del punto de conexión.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_iec104"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc"],
        "content": f"{COMMON_PIPELINE_PREFIX} En el PPC y en el analizador de red se unifican medidas IEC-104, Modbus y eventos de compliance para explicar desvíos en el PCC.",
    },
    {
        "key": "harmonic-events",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["method_quality"], "domain/power-quality", "stack/ppc", "asset/pcc"],
        "content": "El cerebro de calidad de red separa THD, flicker y desequilibrio por ventana temporal para distinguir eventos reales del PCC de ruido de medida o resampling.",
    },
    {
        "key": "compliance-kpis",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc"],
        "content": "Los KPI del PPC combinan disponibilidad del controlador, cumplimiento de reactiva y calidad de red para no mezclar indisponibilidad operativa con eventos de red.",
    },
    {
        "key": "voltage-regulation",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc"],
        "content": "La regulación de tensión en el PCC usa droop configurable y compensación de reactiva para mantener tensión dentro del ±5% de la nominal según código de red.",
    },
    {
        "key": "flicker-analysis",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_quality"], "domain/power-quality", "asset/pcc"],
        "content": "El análisis de flicker calcula Pst y Plt según IEC 61000-4-15, separando contribución de la planta de la preexistente en red para informes de compliance.",
    },
    {
        "key": "reactive-power-modes",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc"],
        "content": "El PPC soporta modos de reactiva: cos-phi fijo, Q fijo, droop V-Q y regulación automática, con transiciones suaves entre modos por cambio de consigna.",
    },
    {
        "key": "protection-events",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/power-quality", "asset/pcc"],
        "content": "Los eventos de protección del PCC (huecos, sobretensiones, pérdida de fase) se registran con forma de onda para análisis post-mortem y reclamaciones a distribuidora.",
    },
    {
        "key": "power-analyzer-integration",
        "memory_type": "architecture",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], "domain/power-quality", "asset/pcc"],
        "content": "El analizador de red ION/Janitza se integra vía Modbus TCP con registros de calidad, formas de onda y eventos, sincronizando con el PPC cada segundo.",
    },
    {
        "key": "curtailment-ppc-interaction",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc", "domain/ems"],
        "content": "El curtailment por calidad de red se activa cuando THD o tensión exceden límites, reduciendo potencia activa gradualmente hasta recuperar compliance.",
    },
    {
        "key": "grid-code-reporting",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "regulation/grid-code"],
        "content": "Los informes de código de red se generan automáticamente con periodos de cumplimiento, violaciones, duración y energía afectada para auditorías regulatorias.",
    },
    {
        "key": "islanding-detection",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/power-quality", "asset/pcc"],
        "content": "La detección de islanding usa método activo (inyección de perturbación) y pasivo (ROCOF, vector shift) para cumplir tiempos de desconexión regulatorios.",
    },
    {
        "key": "harmonic-filter-monitoring",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_condition"], "domain/power-quality"],
        "content": "Los filtros de armónicos se monitorizan midiendo corriente por rama y temperatura de componentes para detectar degradación de condensadores o resistencias.",
    },
    {
        "key": "unbalance-detection",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_quality"], "domain/power-quality", "asset/pcc"],
        "content": "La detección de desequilibrio calcula componentes simétricas y compara secuencia negativa con umbrales para identificar problemas de red o de la propia planta.",
    },
    {
        "key": "fault-ride-through",
        "memory_type": "architecture",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "regulation/grid-code"],
        "content": "El perfil de fault-ride-through define curvas de tensión-tiempo que la planta debe soportar sin desconectarse, con inyección de reactiva durante el hueco.",
    },
    {
        "key": "pq-historian",
        "memory_type": "architecture",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/power-quality"],
        "content": "El historiador de calidad de potencia almacena valores agregados a 10min para compliance y formas de onda a 10kHz para eventos, con retención de 5 años.",
    },
    {
        "key": "measurement-uncertainty",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [ENERGY_TAGS["method_quality"], "domain/power-quality", "asset/pcc"],
        "content": "La incertidumbre de medida del analizador de red se considera en los cálculos de compliance para no penalizar la planta por error instrumental en zona límite.",
    },
    {
        "key": "network-impedance",
        "memory_type": "general",
        "importance": 0.79,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/power-quality", "asset/pcc"],
        "content": "La estimación de impedancia de red en el PCC se actualiza periódicamente para ajustar modelos de interacción armónica y estabilidad del PPC.",
    },
]

_E5_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["metric_availability"], "domain/predictive-maintenance", "asset/inversores"],
        "content": f"{COMMON_METHOD_PREFIX} En mantenimiento predictivo de inversores esta metodología se usa para vigilar IGBT, ventiladores, corrientes por MPPT y temperatura ambiente antes de que aparezca indisponibilidad.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["metric_availability"], "domain/predictive-maintenance", "asset/inversores"],
        "content": f"{COMMON_PIPELINE_PREFIX} En mantenimiento predictivo el pipeline recoge alarmas, temperaturas y corrientes de inversor para construir residuales térmicos y diagnósticos por familia de equipo.",
    },
    {
        "key": "thermal-residuals",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["method_condition"], "domain/predictive-maintenance", "asset/inversores", "metric/thermal-health"],
        "content": "Los residuales térmicos por familia de inversor detectan degradación de ventiladores y IGBT antes de que la potencia disponible caiga de forma visible.",
    },
    {
        "key": "mtbf-availability",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/predictive-maintenance", "asset/inversores", "metric/mtbf"],
        "content": "La visión predictiva separa disponibilidad energética, tiempo medio entre fallos y degradación paulatina para priorizar mantenimiento antes de un disparo duro.",
    },
    {
        "key": "igbt-health-index",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_condition"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El índice de salud IGBT combina ciclos térmicos acumulados, corriente de fuga y tiempo en zona de saturación para estimar vida útil remanente del semiconductor.",
    },
    {
        "key": "fan-degradation",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "La degradación de ventiladores se detecta comparando temperatura de disipador con modelo térmico esperado a misma potencia y temperatura ambiente.",
    },
    {
        "key": "mppt-current-analysis",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El análisis de corrientes por MPPT identifica strings degradados, diodos bypass activos y mismatch severo comparando ratios de corriente entre trackers.",
    },
    {
        "key": "failure-mode-catalog",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["method_condition"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El catálogo de modos de fallo clasifica por subsistema (potencia, control, comunicación, refrigeración) con síntomas observables y acciones correctivas por cada modo.",
    },
    {
        "key": "vibration-analysis",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El análisis de vibración en ventiladores de inversor usa acelerómetros para detectar desbalance, rodamiento degradado y resonancia estructural antes de rotura.",
    },
    {
        "key": "maintenance-scheduling",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/predictive-maintenance"],
        "content": "La programación de mantenimiento combina score predictivo, ventana de baja producción e inventario de repuestos para minimizar impacto en disponibilidad.",
    },
    {
        "key": "spare-parts-inventory",
        "memory_type": "general",
        "importance": 0.79,
        "tags": ["domain/predictive-maintenance", "asset/inversores"],
        "content": "El inventario de repuestos se vincula con tasas de fallo por componente para mantener stock mínimo de IGBT, ventiladores, placas de control y fusibles.",
    },
    {
        "key": "aging-model",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El modelo de envejecimiento usa curvas de Arrhenius para semiconductores y Weibull para componentes mecánicos, actualizando parámetros con datos operativos reales.",
    },
    {
        "key": "warranty-tracking",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/predictive-maintenance", "asset/inversores"],
        "content": "El seguimiento de garantía registra incidencias, reparaciones y reemplazos por número de serie para reclamaciones al fabricante y análisis de fiabilidad por lote.",
    },
    {
        "key": "remote-diagnostics",
        "memory_type": "architecture",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El diagnóstico remoto permite al fabricante acceder a logs internos del inversor vía VPN para análisis detallado sin desplazamiento a planta.",
    },
    {
        "key": "cleaning-impact",
        "memory_type": "general",
        "importance": 0.78,
        "tags": [ENERGY_TAGS["method_quality"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El impacto de limpieza de módulos se cuantifica comparando performance ratio antes y después para validar frecuencia óptima de lavado por zona de planta.",
    },
    {
        "key": "electrical-testing",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_condition"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "Las pruebas eléctricas periódicas incluyen aislamiento, impedancia de bucle, termografía y curvas IV para complementar la monitorización continua online.",
    },
    {
        "key": "alert-prioritization",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/predictive-maintenance"],
        "content": "La priorización de alertas predictivas pondera severidad del fallo potencial, tiempo estimado hasta fallo y coste de parada para ordenar la cola de trabajo.",
    },
    {
        "key": "fleet-benchmarking",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_condition"], "domain/predictive-maintenance", "asset/inversores"],
        "content": "El benchmarking de flota compara rendimiento entre inversores de misma familia y edad para detectar outliers que requieren inspección prioritaria.",
    },
]

_E6_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_iec104"], "domain/ot", "asset/subestacion"],
        "content": f"{COMMON_METHOD_PREFIX} En observabilidad de subestaciones y OT se usa para seguir breaker status, corriente por bahía, temperatura de transformador y señales IEC-104 antes de que se propaguen al resto de activos.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_iec104"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["metric_power_quality"], "domain/ot", "asset/subestacion"],
        "content": f"{COMMON_PIPELINE_PREFIX} En subestaciones y OT el pipeline normaliza IEC-104, alarmas de RTU y medidas de transformador antes de cruzarlas con eventos del PCC y del sistema energético.",
    },
    {
        "key": "breaker-transformer-correlation",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["protocol_iec104"], "domain/ot", "asset/subestacion", "asset/transformador"],
        "content": "La observabilidad OT correlaciona aperturas de breaker, carga de transformador y alarmas de protección para explicar huecos, disparos y pérdidas de disponibilidad.",
    },
    {
        "key": "ot-availability-kpis",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["metric_availability"], ENERGY_TAGS["metric_power_quality"], "domain/ot", "asset/subestacion"],
        "content": "Los KPI OT separan indisponibilidad por comunicaciones, por RTU y por equipo de patio para que la causa raíz no se diluya en la operación de planta.",
    },
    {
        "key": "transformer-monitoring",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot", "asset/transformador"],
        "content": "La monitorización de transformador incluye temperatura de devanado, aceite, gas disuelto (DGA online), nivel de aceite y carga por fase para diagnóstico continuo.",
    },
    {
        "key": "protection-relay-status",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["protocol_iec104"], "domain/ot", "asset/subestacion"],
        "content": "El estado de relés de protección se monitoriza vía IEC-104 para detectar disparos, autorecierres, bloqueos y confirmar coordinación de protecciones.",
    },
    {
        "key": "rtu-health",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["protocol_iec104"], "domain/ot"],
        "content": "La salud de RTU se evalúa por latencia de respuesta, tasa de timeouts, calidad de timestamps y drift de reloj para mantener fiabilidad de datos OT.",
    },
    {
        "key": "cybersecurity-monitoring",
        "memory_type": "architecture",
        "importance": 0.89,
        "tags": ["domain/ot", "asset/subestacion", "concern/security"],
        "content": "La monitorización de ciberseguridad OT detecta tráfico anómalo en la red IEC-104, accesos no autorizados y cambios de configuración no programados en RTU.",
    },
    {
        "key": "bay-current-monitoring",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot", "asset/subestacion"],
        "content": "La corriente por bahía se monitoriza para detectar desequilibrios, sobrecargas y contribución a cortocircuito, alimentando modelos de estado de la subestación.",
    },
    {
        "key": "grounding-monitoring",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot", "asset/subestacion"],
        "content": "La monitorización de puesta a tierra verifica continuidad y resistencia de malla para cumplir normativa de seguridad y protección contra sobretensiones.",
    },
    {
        "key": "iec61850-integration",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/ot", "asset/subestacion"],
        "content": "La integración IEC 61850 permite GOOSE entre relés para protección rápida y MMS para supervisión, coexistiendo con legacy IEC-104 durante migración.",
    },
    {
        "key": "weather-impact-ot",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/ot", "domain/meteorologia"],
        "content": "El impacto meteorológico en OT correlaciona temperatura ambiente con carga de transformador y viento con vibración de línea para anticipar limitaciones.",
    },
    {
        "key": "maintenance-windows",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/ot", "asset/subestacion"],
        "content": "Las ventanas de mantenimiento de subestación se coordinan con operador del sistema, registrando equipos afectados, duración real y disponibilidad residual.",
    },
    {
        "key": "soe-recording",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_iec104"], "domain/ot"],
        "content": "El registro de secuencia de eventos (SOE) con resolución de 1ms permite reconstruir cadena causal de disparos y correlacionar con perturbografía.",
    },
    {
        "key": "aging-infrastructure",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot", "asset/subestacion"],
        "content": "La evaluación de infraestructura envejecida pondera antigüedad, historial de fallos, resultados de ensayos y criticidad para priorizar renovación de equipos.",
    },
    {
        "key": "alarm-rationalization",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot"],
        "content": "La racionalización de alarmas OT reduce ruido agrupando por consecuencia, suprimiendo derivadas y priorizando por impacto operativo para no saturar al operador.",
    },
    {
        "key": "scada-gateway-redundancy",
        "memory_type": "architecture",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/ot", "asset/subestacion"],
        "content": "El gateway SCADA de subestación opera en hot-standby con conmutación automática, verificando coherencia de base de datos entre primario y respaldo.",
    },
    {
        "key": "environmental-monitoring",
        "memory_type": "general",
        "importance": 0.78,
        "tags": [ENERGY_TAGS["method_condition"], "domain/ot", "asset/subestacion"],
        "content": "La monitorización ambiental de subestación mide SF6, ruido, campos electromagnéticos y aceite vertido para cumplimiento ambiental y detección temprana de fugas.",
    },
]

_E7_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], "domain/wind", "asset/aerogenerador", ENERGY_TAGS["metric_availability"]],
        "content": f"{COMMON_METHOD_PREFIX} En el SCADA de parque eólico esta metodología se usa para vigilar pitch, yaw, gearbox, generador y torre antes de que se propaguen indisponibilidades.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], ENERGY_TAGS["protocol_iec104"], "domain/wind", "asset/aerogenerador"],
        "content": f"{COMMON_PIPELINE_PREFIX} En el parque eólico el pipeline unifica SCADA, CMS (condition monitoring system) y datos meteorológicos de la góndola para una visión integral del activo.",
    },
    {
        "key": "pitch-control",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "El control de pitch regula ángulo de pala para limitar potencia en viento alto y optimizar captura en viento bajo, con monitorización de asimetría entre palas.",
    },
    {
        "key": "yaw-optimization",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador"],
        "content": "La optimización de yaw minimiza desalineamiento con dirección de viento usando sensores de góndola y corrección por efecto estela entre turbinas.",
    },
    {
        "key": "gearbox-vibration",
        "memory_type": "general",
        "importance": 0.90,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador", "metric/vibration"],
        "content": "La monitorización de vibración del gearbox analiza espectro de frecuencias para detectar desgaste de rodamientos, dientes agrietados y desalineamiento de ejes.",
    },
    {
        "key": "generator-monitoring",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "La monitorización del generador incluye temperatura de devanados, corriente por fase, aislamiento y vibración de cojinetes para detectar degradación temprana.",
    },
    {
        "key": "tower-structural-health",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador"],
        "content": "La salud estructural de torre se evalúa con acelerómetros midiendo frecuencias naturales y amortiguamiento para detectar fatiga, aflojamiento de pernos y asentamiento.",
    },
    {
        "key": "power-curve-analysis",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["method_quality"], ENERGY_TAGS["metric_availability"], "domain/wind", "asset/aerogenerador"],
        "content": "El análisis de curva de potencia compara producción real vs garantizada por bin de viento para detectar underperformance, suciedad de palas y desajustes de pitch.",
    },
    {
        "key": "wake-effect-modeling",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador"],
        "content": "El modelo de estelas calcula pérdidas por turbina según layout del parque y dirección de viento para optimizar consignas individuales de derating.",
    },
    {
        "key": "ice-detection",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador"],
        "content": "La detección de hielo combina temperatura, humedad, potencia vs esperada y sensor de hielo dedicado para activar calentamiento de palas y parada de seguridad.",
    },
    {
        "key": "lightning-protection",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "La protección contra rayos registra impactos por turbina y monitoriza resistencia de puesta a tierra y continuidad de bajantes para validar integridad del sistema.",
    },
    {
        "key": "cms-integration",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "El CMS (condition monitoring system) se integra con SCADA para correlacionar vibración, temperatura y proceso operativo en diagnósticos automáticos por turbina.",
    },
    {
        "key": "scada-wind-architecture",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/wind", "asset/aerogenerador"],
        "content": "La arquitectura SCADA eólica centraliza datos de turbinas, meteo-torres y subestación en un servidor central con redundancia hot-standby y archivado a 1 segundo.",
    },
    {
        "key": "blade-inspection",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "La inspección de palas combina drones con IA de detección de daño, termografía y ultrasonidos para detectar erosión de borde de ataque, grietas y delaminaciones.",
    },
    {
        "key": "wind-resource-assessment",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [ENERGY_TAGS["method_quality"], "domain/wind", "domain/meteorologia"],
        "content": "La evaluación del recurso eólico compara producción real con P50/P90 del estudio previo para validar modelo de viento y ajustar proyecciones financieras.",
    },
    {
        "key": "noise-compliance",
        "memory_type": "general",
        "importance": 0.78,
        "tags": ["domain/wind", "asset/aerogenerador", "regulation/noise"],
        "content": "El cumplimiento acústico usa modo reducido nocturno con curtailment por turbina según dirección de viento y distancia a receptores sensibles.",
    },
    {
        "key": "availability-categories",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/wind", "asset/aerogenerador"],
        "content": "La disponibilidad eólica separa parada por viento (alto/bajo), mantenimiento programado, fallo de turbina, grid loss y curtailment para análisis granular.",
    },
    {
        "key": "remote-reset-procedures",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["method_condition"], "domain/wind", "asset/aerogenerador"],
        "content": "Los procedimientos de reset remoto permiten reiniciar turbinas tras fallos transitorios sin desplazamiento, registrando causa original y éxito del reset.",
    },
]

_E8_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], ENERGY_TAGS["stack_pipeline"], "domain/curtailment", ENERGY_TAGS["metric_availability"]],
        "content": f"{COMMON_METHOD_PREFIX} En gestión de curtailment esta metodología se usa para clasificar eventos de limitación, cuantificar energía perdida y correlacionar con señales del operador de red.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_iec104"], "domain/curtailment"],
        "content": f"{COMMON_PIPELINE_PREFIX} En curtailment el pipeline recibe señales del operador vía IEC-104, las cruza con producción real y meteorología para calcular energía perdida por evento.",
    },
    {
        "key": "curtailment-classification",
        "memory_type": "general",
        "importance": 0.90,
        "tags": [ENERGY_TAGS["method_quality"], "domain/curtailment"],
        "content": "Los eventos de curtailment se clasifican en: mandado por operador, por ramp-rate, por calidad de red, por precio negativo y por mantenimiento de red.",
    },
    {
        "key": "lost-energy-accounting",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [ENERGY_TAGS["metric_availability"], "domain/curtailment", "metric/energy-yield"],
        "content": "La contabilidad de energía perdida compara producción real con producción potencial (usando irradiancia/viento y modelo de planta) durante cada evento de curtailment.",
    },
    {
        "key": "operator-signal-handling",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": [ENERGY_TAGS["protocol_iec104"], "domain/curtailment", "stack/ppc"],
        "content": "Las señales del operador de red se reciben vía IEC-104 como consignas de potencia activa máxima, con ACK automático y registro de tiempos de cumplimiento.",
    },
    {
        "key": "ramp-down-procedures",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/curtailment", "stack/ppc"],
        "content": "Los procedimientos de ramp-down reducen potencia siguiendo rampa regulatoria (típicamente 10%/min) distribuyendo la reducción entre inversores/turbinas proporcionalmente.",
    },
    {
        "key": "compensation-tracking",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/curtailment", "metric/energy-yield"],
        "content": "El seguimiento de compensación registra energía perdida por curtailment mandado con evidencia para reclamaciones regulatorias y cálculo de lucro cesante.",
    },
    {
        "key": "forecast-integration",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [ENERGY_TAGS["method_quality"], "domain/curtailment", "domain/meteorologia"],
        "content": "La integración con pronóstico meteorológico anticipa periodos de alta producción y posible curtailment para optimizar despacho de BESS y programación de mantenimiento.",
    },
    {
        "key": "market-price-curtailment",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/curtailment", "stack/dispatch"],
        "content": "El curtailment por precio negativo se activa cuando el precio del mercado diario baja del umbral configurable, registrando ahorro vs energía no inyectada.",
    },
    {
        "key": "grid-congestion-analysis",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["method_anomaly"], "domain/curtailment", "domain/power-quality"],
        "content": "El análisis de congestión de red identifica patrones temporales y geográficos de curtailment para negociar con el operador ampliaciones de capacidad.",
    },
    {
        "key": "multi-plant-coordination",
        "memory_type": "architecture",
        "importance": 0.84,
        "tags": ["domain/curtailment", "stack/dispatch"],
        "content": "La coordinación multi-planta distribuye curtailment entre activos del mismo punto de conexión minimizando pérdida total y respetando prioridades contractuales.",
    },
    {
        "key": "regulatory-reporting",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/curtailment", "regulation/grid-code"],
        "content": "Los informes regulatorios de curtailment detallan por evento: hora inicio/fin, tipo, potencia limitada, energía perdida y evidencia de cumplimiento de consigna.",
    },
    {
        "key": "historical-analysis",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [ENERGY_TAGS["method_quality"], "domain/curtailment"],
        "content": "El análisis histórico de curtailment identifica tendencias estacionales, correlación con capacidad de red y evolución interanual para planificación estratégica.",
    },
    {
        "key": "real-time-dashboard",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/curtailment"],
        "content": "El dashboard de curtailment en tiempo real muestra estado de consigna, producción vs potencial, energía perdida acumulada y alarma de curtailment activo por planta.",
    },
    {
        "key": "bess-arbitrage-curtailment",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/curtailment", "asset/bess", "stack/dispatch"],
        "content": "El BESS absorbe excedente durante curtailment mandado para inyectar en hora punta, convirtiendo energía perdida en ingresos de arbitraje.",
    },
    {
        "key": "notification-system",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [ENERGY_TAGS["stack_pipeline"], "domain/curtailment"],
        "content": "El sistema de notificaciones envía alertas de curtailment activo a operadores y gestores con estimación de duración y pérdida económica en tiempo real.",
    },
    {
        "key": "compliance-verification",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [ENERGY_TAGS["metric_power_quality"], "domain/curtailment", "regulation/grid-code"],
        "content": "La verificación de compliance durante curtailment asegura que la planta cumple consigna dentro de la tolerancia y rampa regulatoria, registrando desviaciones.",
    },
    {
        "key": "economic-optimization",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": ["domain/curtailment", "stack/dispatch"],
        "content": "La optimización económica de curtailment decide entre parar producción, cargar BESS o reducir parcialmente según precio de mercado, coste de oportunidad y desgaste.",
    },
]

# ═══════════════════════════════════════════════════════════════════
# SOFTWARE PROJECTS (7)
# ═══════════════════════════════════════════════════════════════════

_S1_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["pattern_rest"], SOFTWARE_TAGS["concern_auth"], SOFTWARE_TAGS["concern_observability"], "domain/backend", "stack/fastapi"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The API gateway serves as the single entry point, handling authentication, rate limiting, and request routing to downstream services.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["concern_testing"], "domain/backend"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The gateway pipeline includes OpenAPI schema validation, integration tests against a test auth provider, and canary deployment to staging before production.",
    },
    {
        "key": "oauth2-flow",
        "memory_type": "architecture",
        "importance": 0.92,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/backend", "stack/fastapi"],
        "content": "The gateway implements OAuth2 authorization code flow with PKCE for SPAs and client_credentials for service-to-service. Tokens are JWTs signed with RS256, validated via JWKS endpoint.",
    },
    {
        "key": "rate-limiting",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend", "stack/redis"],
        "content": "Rate limiting uses a sliding window counter in Redis with configurable limits per API key, endpoint, and IP. The 429 response includes Retry-After and X-RateLimit-Remaining headers.",
    },
    {
        "key": "request-routing",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend", "stack/fastapi"],
        "content": "Request routing uses path-based rules with weighted load balancing. Each downstream service registers its routes and health endpoint. Unhealthy backends are circuit-broken.",
    },
    {
        "key": "jwt-validation",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/backend"],
        "content": "JWT validation checks signature (RS256), expiration, issuer, audience, and required scopes. The JWKS keys are cached in Redis with 1-hour TTL and background refresh.",
    },
    {
        "key": "api-versioning",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend"],
        "content": "API versioning uses URL path prefix (/v1/, /v2/) with a deprecation header. Old versions run for 6 months after successor launch with monitoring of remaining traffic.",
    },
    {
        "key": "cors-configuration",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/backend"],
        "content": "CORS is configured per-origin with allowed methods and headers. Preflight responses are cached for 1 hour. Credentials mode is restricted to known frontend origins.",
    },
    {
        "key": "error-standardization",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend"],
        "content": "All API errors follow RFC 7807 Problem Details format with type, title, status, detail, and instance fields. Error codes are documented in the OpenAPI spec.",
    },
    {
        "key": "request-logging",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/backend"],
        "content": "Request logging captures method, path, status, latency, and correlation ID in structured JSON. PII fields are redacted. Logs feed into ELK stack for analysis.",
    },
    {
        "key": "health-checks",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["pattern_rest"], SOFTWARE_TAGS["concern_observability"], "domain/backend"],
        "content": "Health endpoints expose /health (liveness) and /ready (readiness) with checks for Redis, downstream services, and certificate expiry. Used by K8s probes.",
    },
    {
        "key": "tls-termination",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/backend", SOFTWARE_TAGS["stack_k8s"]],
        "content": "TLS terminates at the ingress controller with automatic cert renewal via cert-manager. Internal traffic between gateway and backends uses mTLS.",
    },
    {
        "key": "circuit-breaker",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend"],
        "content": "Circuit breaker per downstream service opens after 5 consecutive failures, half-opens after 30s for a probe request, and closes on success. State is shared via Redis.",
    },
    {
        "key": "api-key-management",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/backend"],
        "content": "API keys are hashed with SHA-256 and stored in PostgreSQL. Keys support scoping to specific endpoints and rate limit tiers. Rotation is zero-downtime with overlap period.",
    },
    {
        "key": "request-validation",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["pattern_rest"], SOFTWARE_TAGS["concern_data_quality"], "domain/backend"],
        "content": "Request validation uses Pydantic models auto-generated from OpenAPI spec. Invalid requests return 422 with field-level errors. Query params are coerced where safe.",
    },
    {
        "key": "response-caching",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend", "stack/redis"],
        "content": "Response caching uses Redis with Cache-Control directives. Cache keys include user scope to prevent data leakage. Invalidation is event-driven from downstream services.",
    },
    {
        "key": "webhook-delivery",
        "memory_type": "general",
        "importance": 0.80,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/backend"],
        "content": "Webhook delivery sends events to registered URLs with HMAC-SHA256 signatures, exponential retry (5 attempts over 24h), and dead-letter queue for persistent failures.",
    },
    {
        "key": "metrics-exposition",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/backend"],
        "content": "Prometheus metrics expose request count, latency histogram, error rate, and active connections per route. Custom business metrics track auth failures by type.",
    },
    {
        "key": "graceful-shutdown",
        "memory_type": "general",
        "importance": 0.79,
        "tags": [SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["stack_k8s"], "domain/backend"],
        "content": "Graceful shutdown drains in-flight requests for up to 30s, stops accepting new connections, then exits. K8s preStop hook adds 5s delay for endpoint propagation.",
    },
    {
        "key": "openapi-generation",
        "memory_type": "general",
        "importance": 0.81,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend", "stack/fastapi"],
        "content": "OpenAPI spec is auto-generated from FastAPI route definitions and published at /docs. Client SDKs for TypeScript and Python are generated in CI from the spec.",
    },
]

_S2_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["concern_observability"], SOFTWARE_TAGS["concern_testing"], "domain/frontend", "stack/react", "stack/typescript"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The React dashboard provides real-time operational views with WebSocket data streaming, chart components, and role-based access control.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["concern_testing"], "domain/frontend"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The dashboard pipeline includes Storybook visual regression tests, Playwright E2E tests, and Lighthouse CI for performance budgets.",
    },
    {
        "key": "websocket-streaming",
        "memory_type": "architecture",
        "importance": 0.90,
        "tags": ["domain/frontend", "stack/react", "pattern/websocket"],
        "content": "WebSocket connection uses a shared context provider with automatic reconnection, exponential backoff, and message queuing during disconnects. Binary protocol for efficiency.",
    },
    {
        "key": "chart-components",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/frontend", "stack/react", "stack/d3"],
        "content": "Chart components use D3 for rendering with React managing lifecycle. Each chart type (line, bar, heatmap, gauge) is a composable component with shared axis and tooltip logic.",
    },
    {
        "key": "state-management",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": ["domain/frontend", "stack/react", "stack/zustand"],
        "content": "State management uses Zustand stores: authStore for user/tokens, dataStore for real-time feeds, uiStore for layout/filters. Persistence via localStorage for non-sensitive state.",
    },
    {
        "key": "rbac-frontend",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/frontend", "stack/react"],
        "content": "RBAC uses JWT claims to determine visible routes, widgets, and actions. A PermissionGate component wraps protected UI elements. Permissions are cached on login.",
    },
    {
        "key": "responsive-layout",
        "memory_type": "general",
        "importance": 0.82,
        "tags": ["domain/frontend", "stack/react", "stack/tailwind"],
        "content": "The responsive layout uses CSS Grid with breakpoint-aware dashboard panels. Users can rearrange widgets via drag-and-drop with layout persisted per-user in the backend.",
    },
    {
        "key": "data-fetching",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/frontend", "stack/react", "stack/tanstack-query"],
        "content": "Data fetching uses TanStack Query with stale-while-revalidate strategy. Cache time is 5min for reference data, 30s for operational data. Prefetching on route hover.",
    },
    {
        "key": "error-boundaries",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/frontend", "stack/react"],
        "content": "Error boundaries wrap each dashboard panel independently so one failing widget doesn't crash the entire view. Errors are reported to Sentry with component stack trace.",
    },
    {
        "key": "theme-system",
        "memory_type": "general",
        "importance": 0.79,
        "tags": ["domain/frontend", "stack/react", "stack/tailwind"],
        "content": "The theme system supports light/dark modes with CSS custom properties. Energy-domain colors (green/amber/red) are semantic tokens mapped to operational states.",
    },
    {
        "key": "accessibility",
        "memory_type": "general",
        "importance": 0.81,
        "tags": ["domain/frontend", "stack/react", "concern/a11y"],
        "content": "Accessibility follows WCAG 2.1 AA with keyboard navigation, ARIA labels on charts, high-contrast mode, and screen reader announcements for real-time data updates.",
    },
    {
        "key": "performance-budgets",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/frontend", "stack/react", SOFTWARE_TAGS["concern_observability"]],
        "content": "Performance budgets enforce LCP < 2.5s, FID < 100ms, CLS < 0.1. Bundle size is monitored per-route with alerts on regressions. Code splitting by route and heavy deps.",
    },
    {
        "key": "notification-center",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/frontend", "stack/react"],
        "content": "The notification center aggregates WebSocket alerts, system messages, and task updates in a slide-out panel with read/unread state and configurable filters.",
    },
    {
        "key": "export-functionality",
        "memory_type": "general",
        "importance": 0.78,
        "tags": ["domain/frontend", "stack/react"],
        "content": "Dashboard export supports PNG (via html2canvas), CSV (client-side generation), and PDF (server-side rendering). Large exports are queued and delivered via download link.",
    },
    {
        "key": "testing-strategy",
        "memory_type": "architecture",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["concern_testing"], "domain/frontend", "stack/react"],
        "content": "Testing uses Vitest for unit tests, Testing Library for component tests, Playwright for E2E, and Storybook chromatic for visual regression. Coverage target is 80%.",
    },
    {
        "key": "i18n-support",
        "memory_type": "general",
        "importance": 0.79,
        "tags": ["domain/frontend", "stack/react"],
        "content": "Internationalization uses react-i18next with namespace-per-module. Translations are loaded lazily by locale. Date/number formatting respects user locale settings.",
    },
    {
        "key": "api-client-layer",
        "memory_type": "architecture",
        "importance": 0.84,
        "tags": ["domain/frontend", "stack/react", SOFTWARE_TAGS["pattern_rest"]],
        "content": "The API client layer is auto-generated from the gateway's OpenAPI spec using openapi-typescript-codegen. It includes typed request/response interfaces and error handling.",
    },
    {
        "key": "feature-flags",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/frontend", "stack/react"],
        "content": "Feature flags use a LaunchDarkly-compatible client with fallback to environment variables. Flags control widget visibility, experimental features, and gradual rollouts.",
    },
]

_S3_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["concern_data_quality"], SOFTWARE_TAGS["concern_observability"], "domain/data-engineering", "stack/kafka", "stack/spark"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The ETL pipeline ingests events from Kafka, applies schema validation and quality checks in Spark, and writes clean Parquet to the data lake.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["concern_testing"], "domain/data-engineering"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The ETL CI pipeline runs schema compatibility checks, data quality unit tests with synthetic fixtures, and integration tests against a local Kafka+Spark cluster.",
    },
    {
        "key": "kafka-ingestion",
        "memory_type": "architecture",
        "importance": 0.90,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/data-engineering", "stack/kafka"],
        "content": "Kafka ingestion uses consumer groups with exactly-once semantics via idempotent producers and transactional consumers. Partitioning is by entity ID for ordering guarantees.",
    },
    {
        "key": "schema-registry",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering", "stack/kafka"],
        "content": "Schema Registry enforces Avro schemas with backward compatibility. Producers validate against the registry before publishing. Breaking changes require a new topic version.",
    },
    {
        "key": "data-quality-checks",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering", "stack/spark"],
        "content": "Data quality checks run as Spark transformations: null rate thresholds, referential integrity, statistical outlier detection, and freshness SLAs per source.",
    },
    {
        "key": "spark-job-configuration",
        "memory_type": "general",
        "importance": 0.85,
        "tags": ["domain/data-engineering", "stack/spark"],
        "content": "Spark jobs are configured via YAML with resource limits, parallelism, and checkpoint intervals. Dynamic allocation scales executors between min/max based on backlog.",
    },
    {
        "key": "parquet-partitioning",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/data-engineering", "stack/spark", "stack/parquet"],
        "content": "Parquet output is partitioned by date and source with Z-ordered columns for query performance. Small file compaction runs hourly to prevent the small-files problem.",
    },
    {
        "key": "dead-letter-queue",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/data-engineering", "stack/kafka"],
        "content": "Failed records go to a dead-letter topic with original payload, error details, and retry count. A reprocessing job retries DLQ records daily with updated schemas.",
    },
    {
        "key": "backfill-mechanism",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/data-engineering", "stack/spark"],
        "content": "Backfill jobs re-process historical data for a date range using the same Spark transformations. Idempotent writes via merge-on-read prevent duplicate records.",
    },
    {
        "key": "monitoring-alerts",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/data-engineering"],
        "content": "Pipeline monitoring tracks consumer lag, processing latency, record throughput, and quality check pass rate. Alerts fire on lag > 10min or quality drop > 5%.",
    },
    {
        "key": "data-catalog",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering"],
        "content": "The data catalog auto-registers new datasets with schema, lineage, owner, and freshness SLA. Analysts discover data via a search UI with column-level documentation.",
    },
    {
        "key": "data-retention",
        "memory_type": "general",
        "importance": 0.81,
        "tags": ["domain/data-engineering", "stack/parquet"],
        "content": "Data retention policy keeps hot data (90 days) on SSD, warm (1 year) on HDD, and cold (5 years) on object storage. Transition is automatic based on partition date.",
    },
    {
        "key": "incremental-processing",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": ["domain/data-engineering", "stack/spark"],
        "content": "Incremental processing uses watermarks and Kafka offsets to process only new data. Late-arriving records are handled via a grace period of 1 hour before closing a window.",
    },
    {
        "key": "data-lineage",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering"],
        "content": "Data lineage is tracked at column level using OpenLineage events emitted by Spark. The lineage graph shows source→transform→sink for impact analysis and debugging.",
    },
    {
        "key": "testing-with-fixtures",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["concern_testing"], "domain/data-engineering"],
        "content": "ETL tests use synthetic fixtures generated from schema definitions with configurable error injection (nulls, type mismatches, out-of-range values) for quality check validation.",
    },
    {
        "key": "cost-optimization",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/data-engineering", "stack/spark"],
        "content": "Cost optimization uses spot instances for batch jobs, right-sizing Spark executors based on historical usage, and caching frequently-joined reference tables in memory.",
    },
    {
        "key": "schema-evolution",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering", "stack/kafka"],
        "content": "Schema evolution supports adding nullable columns, widening types, and adding defaults. Column removal requires a deprecation period with zero-read verification.",
    },
    {
        "key": "exactly-once-semantics",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/data-engineering", "stack/kafka"],
        "content": "Exactly-once is achieved via Kafka transactions coordinated with Spark checkpoints. In case of failure, the consumer resumes from the last committed offset.",
    },
]

_S4_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["pattern_rest"], SOFTWARE_TAGS["concern_observability"], SOFTWARE_TAGS["concern_testing"], "domain/mlops", "stack/python"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The ML serving platform manages model lifecycle from registry to production, with A/B testing, canary deployments, and real-time monitoring.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["stack_k8s"], "domain/mlops"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The ML pipeline includes model validation tests (accuracy, latency, memory), container scanning, and staged rollout with automatic rollback on metric degradation.",
    },
    {
        "key": "model-registry",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": ["domain/mlops", "stack/mlflow"],
        "content": "The model registry stores versioned model artifacts with metadata (training data hash, hyperparameters, metrics). Promotion from staging to production requires approval.",
    },
    {
        "key": "ab-testing",
        "memory_type": "general",
        "importance": 0.88,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_testing"]],
        "content": "A/B testing splits traffic by percentage with sticky sessions per user. Statistical significance is checked via sequential testing to minimize sample size.",
    },
    {
        "key": "canary-deployment",
        "memory_type": "general",
        "importance": 0.87,
        "tags": ["domain/mlops", SOFTWARE_TAGS["stack_k8s"]],
        "content": "Canary deploys route 5% traffic to new model version, monitoring latency, error rate, and prediction distribution. Auto-rollback triggers on KL divergence > threshold.",
    },
    {
        "key": "feature-store",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_data_quality"]],
        "content": "The feature store serves precomputed features with point-in-time correctness for training and low-latency lookup for inference. Features are versioned and documented.",
    },
    {
        "key": "model-monitoring",
        "memory_type": "general",
        "importance": 0.89,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_observability"]],
        "content": "Model monitoring tracks prediction distribution, feature drift (PSI), accuracy decay, and latency p99. Drift alerts trigger retraining pipeline automatically.",
    },
    {
        "key": "inference-optimization",
        "memory_type": "general",
        "importance": 0.85,
        "tags": ["domain/mlops", "stack/python"],
        "content": "Inference optimization uses ONNX runtime for CPU models, batched inference for throughput, and model quantization (INT8) for latency-sensitive endpoints.",
    },
    {
        "key": "training-pipeline",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": ["domain/mlops", "stack/python"],
        "content": "The training pipeline runs as Argo Workflows with steps for data extraction, feature engineering, training, evaluation, and registry upload. GPU nodes auto-scale.",
    },
    {
        "key": "data-validation",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_data_quality"]],
        "content": "Training data validation checks schema consistency, null rates, class balance, feature correlation, and detects data leakage by comparing train/test distributions.",
    },
    {
        "key": "experiment-tracking",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/mlops", "stack/mlflow"],
        "content": "Experiment tracking logs hyperparameters, metrics, artifacts, and environment for reproducibility. Experiments are organized by project and linked to git commits.",
    },
    {
        "key": "serving-infrastructure",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": ["domain/mlops", SOFTWARE_TAGS["stack_k8s"], SOFTWARE_TAGS["stack_docker"]],
        "content": "Model serving uses KServe with autoscaling (0 to N replicas), request queuing, and GPU/CPU routing. Each model version runs in its own container with resource limits.",
    },
    {
        "key": "model-explainability",
        "memory_type": "general",
        "importance": 0.82,
        "tags": ["domain/mlops", "stack/python"],
        "content": "Model explainability provides SHAP values for feature importance, partial dependence plots, and per-prediction explanations via an async batch endpoint.",
    },
    {
        "key": "bias-detection",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_data_quality"]],
        "content": "Bias detection runs fairness metrics (demographic parity, equalized odds) on validation data. Models failing bias thresholds are blocked from production promotion.",
    },
    {
        "key": "rollback-procedures",
        "memory_type": "general",
        "importance": 0.85,
        "tags": ["domain/mlops", SOFTWARE_TAGS["stack_k8s"]],
        "content": "Rollback is instant via Kubernetes service selector pointing to previous model version deployment. Traffic switches in < 5s with zero-downtime.",
    },
    {
        "key": "cost-tracking",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/mlops", SOFTWARE_TAGS["concern_observability"]],
        "content": "Cost tracking attributes GPU hours and storage to each model/experiment. Monthly reports show cost-per-prediction trending and identify optimization opportunities.",
    },
    {
        "key": "model-versioning",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/mlops", "stack/mlflow"],
        "content": "Model versions follow semantic versioning. Major bumps for architecture changes, minor for retraining with new data, patch for config tweaks. All versions are immutable.",
    },
    {
        "key": "batch-prediction",
        "memory_type": "general",
        "importance": 0.82,
        "tags": ["domain/mlops", "stack/spark"],
        "content": "Batch prediction runs nightly Spark jobs for large-scale inference, writing results to Parquet with prediction timestamp and model version for auditability.",
    },
]

_S5_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["concern_auth"], SOFTWARE_TAGS["concern_testing"], SOFTWARE_TAGS["concern_observability"], "domain/mobile", "stack/flutter"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The Flutter mobile app implements offline-first architecture with local-first data, background sync, push notifications, and biometric authentication.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], "domain/mobile", "stack/flutter"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The mobile pipeline includes Flutter widget tests, integration tests on emulators, Fastlane for app store deployment, and Codemagic CI for both iOS and Android.",
    },
    {
        "key": "offline-first-sync",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": ["domain/mobile", "stack/flutter", "pattern/offline-first"],
        "content": "Offline-first uses Drift (SQLite) for local storage with a sync engine that queues mutations, resolves conflicts via last-writer-wins per field, and batch-syncs on connectivity.",
    },
    {
        "key": "push-notifications",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/mobile", "stack/flutter", "stack/firebase"],
        "content": "Push notifications use Firebase Cloud Messaging with topic-based routing. Silent pushes trigger background sync. Rich notifications include action buttons and deep links.",
    },
    {
        "key": "biometric-auth",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/mobile", "stack/flutter"],
        "content": "Biometric authentication uses local_auth plugin for fingerprint/face unlock. The biometric key protects the refresh token stored in secure enclave (Keychain/Keystore).",
    },
    {
        "key": "state-management-mobile",
        "memory_type": "architecture",
        "importance": 0.87,
        "tags": ["domain/mobile", "stack/flutter", "stack/riverpod"],
        "content": "State management uses Riverpod with family providers for parameterized state. AsyncNotifier handles loading/error/data states. State is persisted to local DB for offline.",
    },
    {
        "key": "navigation-routing",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/mobile", "stack/flutter"],
        "content": "Navigation uses go_router with declarative routing, deep link support, and guard redirects for auth. Bottom tab bar preserves scroll position on tab switch.",
    },
    {
        "key": "api-integration",
        "memory_type": "general",
        "importance": 0.85,
        "tags": ["domain/mobile", "stack/flutter", SOFTWARE_TAGS["pattern_rest"]],
        "content": "API integration uses Dio with interceptors for auth token injection, retry on 401 (token refresh), request/response logging, and connectivity check before requests.",
    },
    {
        "key": "image-caching",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/mobile", "stack/flutter"],
        "content": "Image caching uses cached_network_image with disk cache limit of 200MB and LRU eviction. Thumbnails are generated server-side for bandwidth optimization.",
    },
    {
        "key": "crash-reporting",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/mobile", "stack/flutter"],
        "content": "Crash reporting uses Sentry with breadcrumbs for user flow replay. Non-fatal errors and ANR (Application Not Responding) events are tracked separately with context.",
    },
    {
        "key": "performance-profiling",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/mobile", "stack/flutter"],
        "content": "Performance profiling monitors frame build/render time, jank percentage, and memory usage. CI runs profile mode tests to catch regression before release.",
    },
    {
        "key": "localization",
        "memory_type": "general",
        "importance": 0.79,
        "tags": ["domain/mobile", "stack/flutter"],
        "content": "Localization uses ARB files with gen-l10n for type-safe access. RTL layout support is tested with Arabic locale. Plural and gender forms use ICU message syntax.",
    },
    {
        "key": "secure-storage",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/mobile", "stack/flutter"],
        "content": "Sensitive data (tokens, PII) is stored in flutter_secure_storage backed by Keychain (iOS) and EncryptedSharedPreferences (Android). Non-sensitive prefs use SharedPreferences.",
    },
    {
        "key": "app-update-flow",
        "memory_type": "general",
        "importance": 0.81,
        "tags": ["domain/mobile", "stack/flutter"],
        "content": "App update flow checks version on launch. Force update blocks usage for critical security patches. Soft update shows dismissable banner with changelog.",
    },
    {
        "key": "background-processing",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/mobile", "stack/flutter"],
        "content": "Background processing uses workmanager for periodic sync and firebase_messaging for event-driven wake. iOS background modes are limited to fetch and remote-notification.",
    },
    {
        "key": "testing-strategy-mobile",
        "memory_type": "architecture",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["concern_testing"], "domain/mobile", "stack/flutter"],
        "content": "Testing pyramid: unit tests for business logic, widget tests for UI components, integration tests for flows on emulators. Golden tests for pixel-perfect UI verification.",
    },
    {
        "key": "accessibility-mobile",
        "memory_type": "general",
        "importance": 0.80,
        "tags": ["domain/mobile", "stack/flutter", "concern/a11y"],
        "content": "Accessibility uses Semantics widgets for screen readers, minimum touch target of 48dp, dynamic text scaling support, and high-contrast mode with tested color ratios.",
    },
    {
        "key": "release-management",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["stack_ci"], "domain/mobile"],
        "content": "Releases follow a 2-week cadence with beta track on TestFlight/Play Console. Staged rollout starts at 10% and expands to 100% over 3 days if crash rate stays low.",
    },
]

_S6_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["stack_k8s"], SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["concern_observability"], "domain/devops", "stack/terraform"],
        "content": f"{COMMON_SW_METHOD_PREFIX} Infrastructure is managed as code with Terraform modules for cloud resources, Helm charts for K8s workloads, and GitOps for deployment reconciliation.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], "domain/devops"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The infra pipeline runs terraform plan on PR, applies on merge to main, and runs compliance checks (tfsec, checkov) as mandatory gates.",
    },
    {
        "key": "terraform-modules",
        "memory_type": "architecture",
        "importance": 0.90,
        "tags": ["domain/devops", "stack/terraform"],
        "content": "Terraform modules are versioned in a mono-repo with semantic versioning. Each module has input validation, output documentation, and example usage. State is in S3 with DynamoDB locking.",
    },
    {
        "key": "k8s-cluster-management",
        "memory_type": "architecture",
        "importance": 0.89,
        "tags": ["domain/devops", SOFTWARE_TAGS["stack_k8s"]],
        "content": "K8s clusters use managed service (EKS) with node groups for general workloads, GPU workloads, and system components. Cluster upgrades follow N-1 version policy.",
    },
    {
        "key": "secrets-management",
        "memory_type": "general",
        "importance": 0.90,
        "tags": [SOFTWARE_TAGS["concern_auth"], "domain/devops", "stack/vault"],
        "content": "Secrets are managed in HashiCorp Vault with dynamic secrets for databases and rotating credentials for API keys. K8s pods access secrets via CSI driver, never env vars.",
    },
    {
        "key": "gitops-workflow",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["stack_ci"], "domain/devops", "stack/argocd"],
        "content": "GitOps uses ArgoCD watching a deployment repo. Developers merge to main, CI builds and pushes image, updates the deployment repo, ArgoCD reconciles within 3 minutes.",
    },
    {
        "key": "monitoring-stack",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/devops"],
        "content": "Monitoring uses Prometheus for metrics, Grafana for dashboards, Loki for logs, and Tempo for traces. All are deployed via Helm with persistent storage and retention policies.",
    },
    {
        "key": "network-policies",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["stack_k8s"], "domain/devops", "concern/security"],
        "content": "Network policies enforce zero-trust between namespaces. Each service explicitly declares allowed ingress/egress. DNS egress is restricted to internal DNS + allowlisted external.",
    },
    {
        "key": "cost-management",
        "memory_type": "general",
        "importance": 0.83,
        "tags": ["domain/devops", SOFTWARE_TAGS["concern_observability"]],
        "content": "Cost management uses Kubecost for per-namespace attribution. Spot instances handle 60% of non-critical workloads. Reserved capacity covers baseline with right-sizing reviews monthly.",
    },
    {
        "key": "disaster-recovery",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": ["domain/devops", SOFTWARE_TAGS["stack_k8s"]],
        "content": "Disaster recovery uses Velero for K8s backup, cross-region S3 replication for data, and Terraform state in versioned S3. RTO is 4 hours, RPO is 1 hour.",
    },
    {
        "key": "ci-cd-pipelines",
        "memory_type": "architecture",
        "importance": 0.89,
        "tags": [SOFTWARE_TAGS["stack_ci"], "domain/devops"],
        "content": "CI/CD uses GitHub Actions with reusable workflows. Build step produces multi-arch Docker images. Deploy step updates Helm values in the deployment repo.",
    },
    {
        "key": "ingress-configuration",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["stack_k8s"], "domain/devops"],
        "content": "Ingress uses nginx-ingress with cert-manager for TLS. Rate limiting and WAF rules are configured at the ingress level. Custom error pages for 502/503.",
    },
    {
        "key": "logging-strategy",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/devops"],
        "content": "All services log structured JSON to stdout. Loki collects via promtail DaemonSet. Log levels are configurable at runtime via ConfigMap. PII scrubbing runs in promtail.",
    },
    {
        "key": "security-scanning",
        "memory_type": "general",
        "importance": 0.86,
        "tags": ["domain/devops", "concern/security", SOFTWARE_TAGS["stack_ci"]],
        "content": "Security scanning runs Trivy on images, tfsec on Terraform, and Snyk on dependencies in CI. Critical CVEs block deployment. Weekly full-repo scan for secrets (gitleaks).",
    },
    {
        "key": "dns-management",
        "memory_type": "general",
        "importance": 0.81,
        "tags": ["domain/devops", "stack/terraform"],
        "content": "DNS is managed via Terraform with Route53. External-dns controller auto-creates records for K8s ingresses. TTL is 300s for services, 3600s for static resources.",
    },
    {
        "key": "capacity-planning",
        "memory_type": "general",
        "importance": 0.82,
        "tags": ["domain/devops", SOFTWARE_TAGS["stack_k8s"]],
        "content": "Capacity planning uses historical resource usage trends to size node groups. HPA scales pods, Karpenter provisions nodes. Buffer capacity is 20% above peak.",
    },
    {
        "key": "on-call-runbooks",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/devops"],
        "content": "On-call runbooks are version-controlled Markdown linked from Grafana alerts. Each runbook covers symptoms, diagnosis steps, resolution, and escalation criteria.",
    },
    {
        "key": "environment-parity",
        "memory_type": "general",
        "importance": 0.84,
        "tags": ["domain/devops", "stack/terraform", SOFTWARE_TAGS["stack_k8s"]],
        "content": "Environment parity uses identical Terraform modules for dev/staging/prod with per-environment tfvars. Staging mirrors prod topology at 1/3 scale for realistic testing.",
    },
]

_S7_MEMORIES = [
    {
        "key": "shared-methodology",
        "memory_type": "architecture",
        "importance": 0.97,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["pattern_cqrs"], SOFTWARE_TAGS["concern_observability"], "domain/microservices", "stack/kafka"],
        "content": f"{COMMON_SW_METHOD_PREFIX} The event-driven microservices architecture uses Kafka as the backbone, Saga orchestration for distributed transactions, and schema evolution for contract compatibility.",
    },
    {
        "key": "shared-pipeline",
        "memory_type": "architecture",
        "importance": 0.93,
        "tags": [SOFTWARE_TAGS["stack_ci"], SOFTWARE_TAGS["stack_docker"], SOFTWARE_TAGS["stack_k8s"], "domain/microservices"],
        "content": f"{COMMON_SW_PIPELINE_PREFIX} The microservices pipeline runs contract tests (Pact), integration tests with Testcontainers, and chaos engineering probes before promoting to production.",
    },
    {
        "key": "saga-orchestration",
        "memory_type": "architecture",
        "importance": 0.91,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
        "content": "Saga orchestration uses a centralized orchestrator service that emits commands and listens for events. Compensation actions run in reverse order on failure with idempotency keys.",
    },
    {
        "key": "dead-letter-handling",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices", "stack/kafka"],
        "content": "Dead-letter queues capture events that fail after 3 retries with exponential backoff. A DLQ dashboard shows failed events with replay capability and root cause tagging.",
    },
    {
        "key": "schema-evolution-strategy",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["concern_data_quality"], "domain/microservices", "stack/kafka"],
        "content": "Schema evolution follows Avro backward/forward compatibility. New fields must have defaults. Consumers tolerate unknown fields. Breaking changes use a new event type.",
    },
    {
        "key": "service-mesh",
        "memory_type": "architecture",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["stack_k8s"], "domain/microservices"],
        "content": "Service mesh uses Istio for mTLS between services, traffic shaping, and observability. Sidecar injection is automatic in the microservices namespace.",
    },
    {
        "key": "event-sourcing",
        "memory_type": "general",
        "importance": 0.87,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["pattern_cqrs"], "domain/microservices"],
        "content": "Event sourcing stores domain events as the source of truth. Read models are projected from events. Snapshotting every 100 events prevents slow aggregate reconstruction.",
    },
    {
        "key": "idempotency-handling",
        "memory_type": "general",
        "importance": 0.89,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
        "content": "Idempotency uses a deduplication table with event ID and TTL of 7 days. Producers include a unique idempotency key. Consumers check before processing.",
    },
    {
        "key": "distributed-tracing",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["concern_observability"], "domain/microservices"],
        "content": "Distributed tracing uses OpenTelemetry with W3C trace context propagation. Kafka headers carry trace IDs across async boundaries. Traces feed into Tempo.",
    },
    {
        "key": "api-gateway-integration",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/microservices", "domain/backend"],
        "content": "The API gateway routes external REST requests to internal services. BFF (Backend for Frontend) pattern adapts responses per client (web, mobile) using GraphQL resolvers.",
    },
    {
        "key": "contract-testing",
        "memory_type": "general",
        "importance": 0.86,
        "tags": [SOFTWARE_TAGS["concern_testing"], "domain/microservices"],
        "content": "Contract testing uses Pact to verify producer/consumer compatibility. Contracts are versioned and verified in CI. Breaking contracts block the producer's deployment.",
    },
    {
        "key": "service-discovery",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["stack_k8s"], "domain/microservices"],
        "content": "Service discovery uses K8s DNS with headless services for direct pod communication. External services are registered as ExternalName or via a service registry sidecar.",
    },
    {
        "key": "circuit-breaker-pattern",
        "memory_type": "general",
        "importance": 0.85,
        "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/microservices"],
        "content": "Circuit breaker uses Resilience4j with configurable failure threshold, wait duration, and permitted calls in half-open state. Metrics are exposed to Prometheus.",
    },
    {
        "key": "data-consistency",
        "memory_type": "general",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["pattern_cqrs"], "domain/microservices"],
        "content": "Eventual consistency is the default. Services own their data and publish change events. Cross-service queries use materialized views projected from subscribed events.",
    },
    {
        "key": "deployment-strategy",
        "memory_type": "general",
        "importance": 0.84,
        "tags": [SOFTWARE_TAGS["stack_k8s"], SOFTWARE_TAGS["stack_ci"], "domain/microservices"],
        "content": "Deployment uses rolling updates with maxSurge=1, maxUnavailable=0. Readiness probes gate traffic. Blue-green is used for database-schema-changing deployments.",
    },
    {
        "key": "chaos-engineering",
        "memory_type": "general",
        "importance": 0.83,
        "tags": [SOFTWARE_TAGS["concern_testing"], "domain/microservices"],
        "content": "Chaos engineering uses LitmusChaos for pod kill, network latency injection, and Kafka broker failure. Game days run monthly targeting one service boundary.",
    },
    {
        "key": "event-catalog",
        "memory_type": "general",
        "importance": 0.82,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
        "content": "The event catalog documents all event types with schema, producers, consumers, and example payloads. Auto-generated from schema registry and AsyncAPI specs.",
    },
    {
        "key": "domain-boundaries",
        "memory_type": "architecture",
        "importance": 0.88,
        "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
        "content": "Domain boundaries follow bounded contexts from DDD. Each service owns one context with its own database. Cross-context communication is event-only, never shared DB.",
    },
]


# ═══════════════════════════════════════════════════════════════════
# PROJECT CATALOG ASSEMBLY
# ═══════════════════════════════════════════════════════════════════

def _make_energy_project(
    slug: str,
    memories: list[dict],
    decision: dict,
    error: dict,
    session: dict,
) -> dict[str, Any]:
    return {"slug": slug, "memories": memories, "decision": decision, "error": error, "session": session}


def _make_session(
    goal: str, outcome: str, summary: str, changes: list[str],
    decisions: list[dict], errors: list[dict], follow_ups: list[dict], tags: list[str],
) -> dict[str, Any]:
    return {
        "agent_id": "bench-seed",
        "goal": goal,
        "outcome": outcome,
        "summary": summary,
        "changes": changes,
        "decisions": decisions,
        "errors": errors,
        "follow_ups": follow_ups,
        "tags": tags,
    }


PROJECT_CATALOG: list[dict[str, Any]] = [
    # ── E1: EMS Fotovoltaica ───────────────────────────────────────
    _make_energy_project(
        slug="bench-ems-fotovoltaica",
        memories=_E1_MEMORIES,
        decision={
            "title": "Muestreo unificado a 1 minuto para EMS fotovoltaico",
            "decision": "Se normaliza la telemetría del EMS y del PPC a un paso de 1 minuto antes del historiado operativo.",
            "rationale": "Reduce desfases entre consignas, meteorología y medidas de red.",
            "alternatives": "Mantener tasas distintas por dispositivo y reconciliar offline elevaba complejidad.",
            "tags": [ENERGY_TAGS["stack_pipeline"], ENERGY_TAGS["protocol_modbus"], "domain/ems", "stack/ppc"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "ems-reactiva-signo-invertido",
            "error_description": "El signo de potencia reactiva quedó invertido entre EMS y PPC y el sistema aplicó consignas erróneas.",
            "solution": "Se fijó una tabla de normalización de signo por fabricante y comprobación diaria contra PCC.",
            "tags": [ENERGY_TAGS["metric_power_quality"], ENERGY_TAGS["protocol_modbus"], "domain/ems", "stack/ppc"],
        },
        session=_make_session(
            goal="Alinear EMS, PPC y meteorología de planta fotovoltaica",
            outcome="Lectura común de disponibilidad, clipping y reactiva establecida.",
            summary="Consolidación de metodología común para EMS fotovoltaico con condition monitoring, QA/QC temporal y anomaly detection.",
            changes=["Unificado pipeline a 1 minuto.", "Añadida correlación irradiancia-clipping-rampas."],
            decisions=[{"title": "Normalizar paso temporal del EMS", "decision": "1 minuto como granularidad operativa.", "rationale": "Permite comparar consignas y meteorología sin desfases."}],
            errors=[{"error_signature": "ems-reactiva-signo-invertido", "description": "Signo invertido de reactiva.", "solution": "Normalización por fabricante."}],
            follow_ups=[{"title": "Extender detección de clipping por bloque", "state": "pending", "details": "Agregar correlación por tracker y SCB."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], "domain/ems"],
        ),
    ),
    # ── E2: Estaciones Meteorológicas ──────────────────────────────
    _make_energy_project(
        slug="bench-estaciones-meteorologicas",
        memories=_E2_MEMORIES,
        decision={
            "title": "Validación cruzada entre piranómetro y referencia satelital",
            "decision": "Las reglas de plausibilidad combinan sensor de campo y referencia externa antes de aceptar irradiancia.",
            "rationale": "Reduce falsas conclusiones sobre suciedad o clipping cuando un solo sensor deriva.",
            "alternatives": "Solo umbrales físicos dejaba pasar drift lento y offsets persistentes.",
            "tags": [ENERGY_TAGS["method_quality"], ENERGY_TAGS["method_anomaly"], "domain/meteorologia"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "meteo-piranometro-sombreado",
            "error_description": "El piranómetro principal quedó sombreado y el pipeline aceptó irradiancia baja como nube real.",
            "solution": "Comparación obligatoria con célula de referencia y detector de asimetría diurna.",
            "tags": [ENERGY_TAGS["method_quality"], "domain/meteorologia"],
        },
        session=_make_session(
            goal="Mejorar QA/QC de estaciones meteorológicas",
            outcome="Metodología operativa de validación de sensores y disponibilidad.",
            summary="Consolidación de condition monitoring y QA/QC temporal para estaciones meteorológicas.",
            changes=["Añadida validación cruzada con satélite.", "Separada disponibilidad por sensor y gateway."],
            decisions=[{"title": "Cruzar irradiancia con referencia externa", "decision": "Dato crítico requiere dos fuentes coherentes.", "rationale": "Evita propagar sensores degradados."}],
            errors=[{"error_signature": "meteo-piranometro-sombreado", "description": "Sombra parcial sobre piranómetro.", "solution": "Cruce con célula de referencia."}],
            follow_ups=[{"title": "Añadir detección de anemómetro atascado", "state": "pending", "details": "Extender reglas para campañas invernales."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_quality"], "domain/meteorologia"],
        ),
    ),
    # ── E3: SCADA Híbrido Solar+BESS ──────────────────────────────
    _make_energy_project(
        slug="bench-scada-hibrido-solar-bess",
        memories=_E3_MEMORIES,
        decision={
            "title": "Priorizar ramp-rate compliance en el SCADA híbrido",
            "decision": "El SCADA antepone cumplimiento de rampa y estabilidad del SoC a consignas agresivas.",
            "rationale": "Evita oscilaciones de consignas y estrés térmico en PCS e inversores.",
            "alternatives": "Forzar setpoint nominal generaba más eventos de limitación.",
            "tags": [ENERGY_TAGS["metric_power_quality"], "domain/scada", "asset/bess"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "scada-bess-desfase-timestamps",
            "error_description": "El BESS publicaba timestamps con desfase y el SCADA interpretó transferencias fuera de secuencia.",
            "solution": "Sincronización NTP obligatoria y descarte de paquetes con deriva > 2 segundos.",
            "tags": [ENERGY_TAGS["stack_pipeline"], "domain/scada", "asset/bess"],
        },
        session=_make_session(
            goal="Estabilizar cerebro operativo para SCADA híbrido solar+BESS",
            outcome="Dataset enlazado con EMS, PPC y mantenimiento predictivo.",
            summary="Consolidación de metodología, pipeline y criterios de despacho para SCADA híbrido.",
            changes=["Normalizada telemetría de PCS e inversores.", "Reforzada lectura de ramp-rate y SoC."],
            decisions=[{"title": "Rampa primero, setpoint después", "decision": "Compliance de rampa como prioridad.", "rationale": "Minimiza oscilaciones."}],
            errors=[{"error_signature": "scada-bess-desfase-timestamps", "description": "Desfase temporal BESS-solar.", "solution": "NTP y descarte fuera de ventana."}],
            follow_ups=[{"title": "Correlacionar alarmas PCS con temperatura ambiente", "state": "pending", "details": "Añadir contexto meteo al diagnóstico."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["stack_pipeline"], "domain/scada", "asset/bess"],
        ),
    ),
    # ── E4: Calidad de Red y PPC ──────────────────────────────────
    _make_energy_project(
        slug="bench-calidad-red-ppc",
        memories=_E4_MEMORIES,
        decision={
            "title": "Separar ventanas lenta y rápida para eventos de calidad de red",
            "decision": "Ventana rápida para detección y lenta para consolidación de compliance.",
            "rationale": "Reduce falsos positivos de armónicos sin perder trazabilidad.",
            "alternatives": "Una única ventana temporal mezclaba ruido transitorio con eventos persistentes.",
            "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality", "stack/ppc"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "ppc-armonicos-ventana-incorrecta",
            "error_description": "Cálculo de armónicos con ventana incorrecta generó alarmas de THD inexistentes.",
            "solution": "Alineación de ventana con analizador de red y bloqueo de comparaciones con resampling inconsistente.",
            "tags": [ENERGY_TAGS["metric_power_quality"], "domain/power-quality"],
        },
        session=_make_session(
            goal="Integrar calidad de red y PPC en el cerebro",
            outcome="Conexión entre compliance, telemetría y metodología compartida.",
            summary="Consolidación de calidad de red y PPC con metodología compartida y KPI coherentes.",
            changes=["Normalizados eventos IEC-104 y medidas Modbus.", "Separada detección rápida y consolidación lenta."],
            decisions=[{"title": "Dos ventanas para calidad de red", "decision": "Separar detección y consolidación.", "rationale": "Evita falsos positivos."}],
            errors=[{"error_signature": "ppc-armonicos-ventana-incorrecta", "description": "THD falso por ventana incorrecta.", "solution": "Alinear con analizador de red."}],
            follow_ups=[{"title": "Correlacionar huecos con breaker upstream", "state": "pending", "details": "Cruzar PCC con OT de subestación."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["metric_power_quality"], "domain/power-quality"],
        ),
    ),
    # ── E5: Mantenimiento Predictivo ──────────────────────────────
    _make_energy_project(
        slug="bench-mantenimiento-predictivo",
        memories=_E5_MEMORIES,
        decision={
            "title": "Usar residuales térmicos por familia de inversor",
            "decision": "Mantenimiento predictivo agrupa inversores por familia eléctrica para residuales térmicos.",
            "rationale": "Comparar equipos equivalentes reduce falsos positivos.",
            "alternatives": "Umbrales fijos por temperatura no diferenciaban operación intensa de degradación.",
            "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/predictive-maintenance"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "predictivo-termistor-desplazado",
            "error_description": "Un termistor desplazado generó alarmas térmicas falsas marcando inversores como degradados.",
            "solution": "Comparación con temperatura de carcasa y potencia para invalidar sensores fuera de rango.",
            "tags": [ENERGY_TAGS["method_quality"], "domain/predictive-maintenance", "asset/inversores"],
        },
        session=_make_session(
            goal="Conectar mantenimiento predictivo con el resto del cerebro",
            outcome="Relación trazada con EMS, estaciones meteo y observabilidad OT.",
            summary="Refuerzo de condition monitoring y anomaly detection para inversores con impacto en disponibilidad.",
            changes=["Añadidos residuales térmicos por familia.", "Conectada indisponibilidad con señales predictivas."],
            decisions=[{"title": "Agrupar por familia eléctrica", "decision": "Alertas entre equipos equivalentes.", "rationale": "Disminuye falsos positivos."}],
            errors=[{"error_signature": "predictivo-termistor-desplazado", "description": "Termistor desplazado.", "solution": "Cruce con carcasa y potencia."}],
            follow_ups=[{"title": "Cruzar fallos térmicos con calidad de red", "state": "pending", "details": "Buscar relación con PCC y transformador."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["metric_availability"], "domain/predictive-maintenance"],
        ),
    ),
    # ── E6: Observabilidad Subestaciones ──────────────────────────
    _make_energy_project(
        slug="bench-observabilidad-subestaciones",
        memories=_E6_MEMORIES,
        decision={
            "title": "Normalizar IEC-104 antes del enriquecimiento OT",
            "decision": "Toda señal IEC-104 se normaliza y timestampa antes de mezclarse con contexto OT.",
            "rationale": "Sin base temporal estable la correlación OT con PPC y EMS pierde trazabilidad.",
            "alternatives": "Enriquecer antes de normalizar generaba secuencias incoherentes.",
            "tags": [ENERGY_TAGS["protocol_iec104"], ENERGY_TAGS["stack_pipeline"], "domain/ot"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "ot-spontaneous-flood",
            "error_description": "RTU OT envió avalancha de spontaneous events sin calidad válida saturando alarmas.",
            "solution": "Validación de calidad IEC-104, deduplicación por secuencia y límite por ventana temporal.",
            "tags": [ENERGY_TAGS["protocol_iec104"], ENERGY_TAGS["method_quality"], "domain/ot"],
        },
        session=_make_session(
            goal="Conectar subestaciones y OT con el cerebro energético",
            outcome="Capa OT integrada con calidad de red, EMS y mantenimiento.",
            summary="Conexión de observabilidad OT con metodología compartida y eventos de red.",
            changes=["Normalizadas señales IEC-104.", "Enlazados eventos OT con calidad de red."],
            decisions=[{"title": "Normalizar IEC-104 primero", "decision": "Limpiar y timestampar antes de enriquecer.", "rationale": "Evita secuencias incoherentes."}],
            errors=[{"error_signature": "ot-spontaneous-flood", "description": "Avalancha de events sin calidad.", "solution": "Validación y deduplicación."}],
            follow_ups=[{"title": "Cruzar alarmas de bahía con disponibilidad EMS", "state": "pending", "details": "Correlación automática OT-operación."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["protocol_iec104"], "domain/ot"],
        ),
    ),
    # ── E7: Parque Eólico SCADA ───────────────────────────────────
    _make_energy_project(
        slug="bench-parque-eolico-scada",
        memories=_E7_MEMORIES,
        decision={
            "title": "Integrar CMS con SCADA para diagnósticos automáticos",
            "decision": "El CMS se integra nativamente con SCADA para correlacionar vibración con proceso operativo.",
            "rationale": "Diagnósticos manuales perdían contexto operativo y tardaban en detectar degradación.",
            "alternatives": "CMS standalone requería exportar datos y cruzar offline con SCADA.",
            "tags": [ENERGY_TAGS["method_condition"], ENERGY_TAGS["stack_pipeline"], "domain/wind"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "wind-yaw-misalignment-persistent",
            "error_description": "Yaw misalignment persistente pasó desapercibido porque el sensor de dirección en góndola tenía offset.",
            "solution": "Cruce de dirección en góndola con meteo-torre y validación por producción relativa entre turbinas.",
            "tags": [ENERGY_TAGS["method_anomaly"], "domain/wind", "asset/aerogenerador"],
        },
        session=_make_session(
            goal="Integrar SCADA eólico con meteorología y CMS",
            outcome="Visión integrada de turbinas, recurso eólico y estado mecánico.",
            summary="Consolidación de monitorización eólica con pitch, yaw, vibración y disponibilidad.",
            changes=["Integrado CMS con SCADA.", "Añadida correlación yaw con meteo-torre."],
            decisions=[{"title": "CMS integrado en SCADA", "decision": "Vibración correlacionada con proceso en tiempo real.", "rationale": "Diagnósticos más rápidos y precisos."}],
            errors=[{"error_signature": "wind-yaw-misalignment-persistent", "description": "Yaw con offset persistente.", "solution": "Cruce con meteo-torre y producción relativa."}],
            follow_ups=[{"title": "Añadir detección de hielo por comparación de curva de potencia", "state": "pending", "details": "Complementar sensor de hielo con analítica."}],
            tags=[ENERGY_TAGS["method_condition"], ENERGY_TAGS["method_anomaly"], "domain/wind"],
        ),
    ),
    # ── E8: Gestión Curtailment ───────────────────────────────────
    _make_energy_project(
        slug="bench-gestion-curtailment",
        memories=_E8_MEMORIES,
        decision={
            "title": "Clasificar curtailment por origen para contabilidad separada",
            "decision": "Los eventos se clasifican por origen (operador, ramp-rate, calidad, precio, mantenimiento) con contabilidad separada.",
            "rationale": "Permite reclamar compensación por curtailment mandado y optimizar el voluntario.",
            "alternatives": "Agrupar todo como curtailment genérico impedía distinguir causas y acciones.",
            "tags": [ENERGY_TAGS["method_quality"], "domain/curtailment"],
            "agent_id": "bench-seed",
        },
        error={
            "error_signature": "curtailment-energia-perdida-sobreestimada",
            "error_description": "La energía perdida por curtailment se sobreestimó porque el modelo de producción potencial no descontaba soiling.",
            "solution": "Incorporar factor de soiling y disponibilidad real en el modelo de producción potencial.",
            "tags": ["domain/curtailment", ENERGY_TAGS["method_quality"]],
        },
        session=_make_session(
            goal="Establecer sistema de gestión de curtailment",
            outcome="Clasificación, contabilidad y optimización de curtailment operativas.",
            summary="Consolidación de gestión de curtailment con clasificación por origen y contabilidad de energía perdida.",
            changes=["Clasificados eventos por origen.", "Integrado BESS para absorción de excedente."],
            decisions=[{"title": "Clasificar por origen", "decision": "Contabilidad separada por tipo de curtailment.", "rationale": "Permite reclamaciones y optimización diferenciada."}],
            errors=[{"error_signature": "curtailment-energia-perdida-sobreestimada", "description": "Sobreestimación de energía perdida.", "solution": "Incluir soiling en modelo potencial."}],
            follow_ups=[{"title": "Integrar predicción de curtailment con mercado", "state": "pending", "details": "Anticipar limitaciones para optimizar BESS."}],
            tags=[ENERGY_TAGS["method_quality"], "domain/curtailment"],
        ),
    ),
    # ── S1: API Gateway Auth ──────────────────────────────────────
    {
        "slug": "bench-api-gateway-auth",
        "memories": _S1_MEMORIES,
        "decision": {
            "title": "Use sliding window for rate limiting instead of fixed window",
            "decision": "Rate limiting uses sliding window counter in Redis for smoother traffic shaping.",
            "rationale": "Fixed window caused burst-then-block patterns at window boundaries.",
            "alternatives": "Token bucket was considered but sliding window is simpler and sufficient.",
            "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend", "stack/redis"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "gateway-429-false-positive",
            "error_description": "Rate limiter returned 429 for authenticated users due to shared counter across API key scopes.",
            "solution": "Changed rate limit key to include both API key and endpoint path for proper isolation.",
            "tags": [SOFTWARE_TAGS["pattern_rest"], "domain/backend"],
        },
        "session": _make_session(
            goal="Harden API gateway authentication and rate limiting",
            outcome="OAuth2+PKCE flow stable, rate limiting isolated per scope.",
            summary="Consolidated authentication flows and rate limiting with proper isolation and monitoring.",
            changes=["Fixed rate limit key to include scope.", "Added JWKS cache with background refresh."],
            decisions=[{"title": "Sliding window rate limiting", "decision": "Redis-backed sliding window per key+endpoint.", "rationale": "Smoother than fixed window."}],
            errors=[{"error_signature": "gateway-429-false-positive", "description": "429 for valid users.", "solution": "Scope-aware rate limit keys."}],
            follow_ups=[{"title": "Add per-user rate limiting tier", "state": "pending", "details": "Support premium users with higher limits."}],
            tags=[SOFTWARE_TAGS["concern_auth"], SOFTWARE_TAGS["pattern_rest"], "domain/backend"],
        ),
    },
    # ── S2: React Dashboard ───────────────────────────────────────
    {
        "slug": "bench-react-dashboard",
        "memories": _S2_MEMORIES,
        "decision": {
            "title": "Use Zustand over Redux for state management",
            "decision": "Zustand for state management with separate stores per domain concern.",
            "rationale": "Less boilerplate, better TypeScript inference, and simpler testing than Redux Toolkit.",
            "alternatives": "Redux Toolkit was familiar but added too much ceremony for our use case.",
            "tags": ["domain/frontend", "stack/react", "stack/zustand"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "dashboard-websocket-memory-leak",
            "error_description": "WebSocket reconnection logic created new listeners without cleaning up old ones, causing memory leak.",
            "solution": "Added cleanup in useEffect return and listener deduplication by event type in the WS provider.",
            "tags": ["domain/frontend", "stack/react", "pattern/websocket"],
        },
        "session": _make_session(
            goal="Stabilize real-time dashboard with WebSocket streaming",
            outcome="WebSocket connection resilient, no memory leaks, charts update smoothly.",
            summary="Fixed WebSocket lifecycle management and optimized chart rendering for real-time data.",
            changes=["Fixed WS listener cleanup.", "Added binary protocol for efficiency."],
            decisions=[{"title": "Zustand over Redux", "decision": "Separate Zustand stores per domain.", "rationale": "Less boilerplate, better DX."}],
            errors=[{"error_signature": "dashboard-websocket-memory-leak", "description": "WS listener leak.", "solution": "Cleanup in useEffect + dedup."}],
            follow_ups=[{"title": "Add offline indicator and queue", "state": "pending", "details": "Show connection status and queue user actions during disconnect."}],
            tags=["domain/frontend", "stack/react", SOFTWARE_TAGS["concern_observability"]],
        ),
    },
    # ── S3: Data Pipeline ETL ─────────────────────────────────────
    {
        "slug": "bench-data-pipeline-etl",
        "memories": _S3_MEMORIES,
        "decision": {
            "title": "Use Avro with Schema Registry over plain JSON",
            "decision": "All Kafka messages use Avro with Schema Registry for enforced contracts.",
            "rationale": "JSON messages caused silent schema drift that broke downstream consumers.",
            "alternatives": "Protobuf was considered but Avro's schema evolution is more flexible for our needs.",
            "tags": [SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["concern_data_quality"], "stack/kafka"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "etl-duplicate-records-after-rebalance",
            "error_description": "Kafka consumer rebalance caused duplicate records in Parquet when offsets weren't committed before partition revocation.",
            "solution": "Implemented cooperative rebalancing and transactional offset commits tied to Spark checkpoints.",
            "tags": [SOFTWARE_TAGS["pattern_event_driven"], "stack/kafka", "stack/spark"],
        },
        "session": _make_session(
            goal="Fix data quality issues in ETL pipeline",
            outcome="Zero duplicate records, schema evolution working, data quality checks passing.",
            summary="Resolved duplicate records from rebalancing and enforced Avro schemas across all topics.",
            changes=["Implemented cooperative rebalancing.", "Added Avro schema enforcement."],
            decisions=[{"title": "Avro + Schema Registry", "decision": "Enforced schemas on all topics.", "rationale": "Prevents silent schema drift."}],
            errors=[{"error_signature": "etl-duplicate-records-after-rebalance", "description": "Dupes after rebalance.", "solution": "Cooperative rebalancing + transactional commits."}],
            follow_ups=[{"title": "Add data freshness SLA monitoring", "state": "pending", "details": "Alert when source data arrives late."}],
            tags=[SOFTWARE_TAGS["pattern_event_driven"], SOFTWARE_TAGS["concern_data_quality"], "domain/data-engineering"],
        ),
    },
    # ── S4: ML Model Serving ──────────────────────────────────────
    {
        "slug": "bench-ml-model-serving",
        "memories": _S4_MEMORIES,
        "decision": {
            "title": "Use KServe over custom serving solution",
            "decision": "KServe for model serving with autoscaling and multi-framework support.",
            "rationale": "Custom serving required maintaining inference servers for each framework separately.",
            "alternatives": "Seldon Core was considered but KServe had better K8s native integration.",
            "tags": ["domain/mlops", SOFTWARE_TAGS["stack_k8s"]],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "ml-serving-cold-start-timeout",
            "error_description": "Scale-from-zero cold start took >30s causing gateway timeouts for first request after idle period.",
            "solution": "Set minReplicas=1 for production models and added warm-up probe that sends sample inference on startup.",
            "tags": ["domain/mlops", SOFTWARE_TAGS["stack_k8s"]],
        },
        "session": _make_session(
            goal="Deploy model serving with A/B testing and monitoring",
            outcome="KServe running, canary deployment working, drift monitoring active.",
            summary="Set up ML serving platform with KServe, canary deployments, and model monitoring.",
            changes=["Deployed KServe with autoscaling.", "Added canary routing with auto-rollback."],
            decisions=[{"title": "KServe for serving", "decision": "Kubernetes-native model serving.", "rationale": "Better K8s integration than alternatives."}],
            errors=[{"error_signature": "ml-serving-cold-start-timeout", "description": "Cold start timeout.", "solution": "minReplicas=1 + warm-up probe."}],
            follow_ups=[{"title": "Implement shadow mode for new models", "state": "pending", "details": "Run new model in parallel without serving traffic."}],
            tags=["domain/mlops", SOFTWARE_TAGS["stack_k8s"], SOFTWARE_TAGS["concern_observability"]],
        ),
    },
    # ── S5: Mobile App Flutter ────────────────────────────────────
    {
        "slug": "bench-mobile-app-flutter",
        "memories": _S5_MEMORIES,
        "decision": {
            "title": "Use Drift (SQLite) for offline-first local storage",
            "decision": "Drift with SQLite for typed local storage with reactive queries and migration support.",
            "rationale": "Hive lacked relational queries and migrations. Isar was too new and unstable.",
            "alternatives": "Hive was simpler but couldn't handle our relational data model for offline sync.",
            "tags": ["domain/mobile", "stack/flutter", "pattern/offline-first"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "mobile-sync-conflict-data-loss",
            "error_description": "Sync conflict resolution overwrote newer server data with stale local changes due to clock skew on device.",
            "solution": "Switched from timestamp-based to vector-clock conflict resolution with server-authoritative merge.",
            "tags": ["domain/mobile", "pattern/offline-first"],
        },
        "session": _make_session(
            goal="Fix offline sync conflicts and biometric auth",
            outcome="Sync conflicts resolved without data loss, biometric auth working on both platforms.",
            summary="Resolved sync data loss with vector clocks and secured token storage with biometrics.",
            changes=["Vector-clock conflict resolution.", "Biometric-protected refresh token."],
            decisions=[{"title": "Drift for offline storage", "decision": "SQLite-backed typed storage.", "rationale": "Supports relational queries and migrations."}],
            errors=[{"error_signature": "mobile-sync-conflict-data-loss", "description": "Sync overwrote server data.", "solution": "Vector clocks + server-authoritative merge."}],
            follow_ups=[{"title": "Add conflict resolution UI", "state": "pending", "details": "Show user merge conflicts for manual resolution."}],
            tags=["domain/mobile", "stack/flutter", SOFTWARE_TAGS["concern_auth"]],
        ),
    },
    # ── S6: Infra Terraform K8s ───────────────────────────────────
    {
        "slug": "bench-infra-terraform-k8s",
        "memories": _S6_MEMORIES,
        "decision": {
            "title": "Use ArgoCD for GitOps deployment reconciliation",
            "decision": "ArgoCD watches deployment repo and reconciles K8s state within 3 minutes.",
            "rationale": "Push-based CD was fragile with webhook failures. GitOps gives declarative desired state.",
            "alternatives": "Flux was considered but ArgoCD's UI and multi-cluster support was better.",
            "tags": [SOFTWARE_TAGS["stack_ci"], "domain/devops", "stack/argocd"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "infra-terraform-state-lock-stuck",
            "error_description": "DynamoDB state lock got stuck after CI runner crashed mid-apply, blocking all terraform operations.",
            "solution": "Added force-unlock step in CI with notification, and a dead-man's switch that releases locks after 30 minutes.",
            "tags": ["domain/devops", "stack/terraform"],
        },
        "session": _make_session(
            goal="Set up GitOps workflow with ArgoCD and harden Terraform CI",
            outcome="ArgoCD reconciling, Terraform state locks handled, security scanning in CI.",
            summary="Deployed GitOps with ArgoCD, fixed Terraform state locking, added security scanning gates.",
            changes=["Deployed ArgoCD with auto-sync.", "Added state lock dead-man's switch."],
            decisions=[{"title": "ArgoCD for GitOps", "decision": "Declarative deployment via git.", "rationale": "More reliable than push-based CD."}],
            errors=[{"error_signature": "infra-terraform-state-lock-stuck", "description": "Stuck state lock.", "solution": "Dead-man's switch after 30min."}],
            follow_ups=[{"title": "Add Terraform drift detection", "state": "blocked", "details": "Detect manual changes not in code. Blocked by multi-account setup."}],
            tags=[SOFTWARE_TAGS["stack_ci"], "domain/devops", SOFTWARE_TAGS["stack_k8s"]],
        ),
    },
    # ── S7: Event-Driven Microservices ────────────────────────────
    {
        "slug": "bench-event-driven-microservices",
        "memories": _S7_MEMORIES,
        "decision": {
            "title": "Use saga orchestration over choreography",
            "decision": "Centralized saga orchestrator manages distributed transactions with explicit compensation.",
            "rationale": "Choreography with events was hard to debug and lacked visibility into transaction state.",
            "alternatives": "Event choreography was simpler but the implicit flow was impossible to trace in production.",
            "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
            "agent_id": "bench-seed",
        },
        "error": {
            "error_signature": "microservices-saga-compensation-loop",
            "error_description": "Saga compensation triggered a new event that re-triggered the original saga, creating an infinite loop.",
            "solution": "Added saga correlation ID to all events and a compensation guard that checks if event originated from compensation.",
            "tags": [SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices"],
        },
        "session": _make_session(
            goal="Fix saga orchestration and add schema evolution",
            outcome="Sagas running without loops, schema evolution enforced, DLQ operational.",
            summary="Resolved saga compensation loop and established schema evolution strategy with Avro.",
            changes=["Added saga correlation ID guard.", "Enforced Avro schema compatibility."],
            decisions=[{"title": "Saga orchestration over choreography", "decision": "Centralized orchestrator for distributed tx.", "rationale": "Better debuggability and visibility."}],
            errors=[{"error_signature": "microservices-saga-compensation-loop", "description": "Infinite compensation loop.", "solution": "Correlation ID guard on compensation events."}],
            follow_ups=[{"title": "Add circuit breaker to orchestrator", "state": "pending", "details": "Prevent cascade when downstream service is down."}],
            tags=[SOFTWARE_TAGS["pattern_event_driven"], "domain/microservices", SOFTWARE_TAGS["concern_observability"]],
        ),
    },
]


# ═══════════════════════════════════════════════════════════════════
# BRIDGES & RELATIONS
# ═══════════════════════════════════════════════════════════════════

PROJECT_BRIDGES = [
    # Energy bridges
    ("bench-ems-fotovoltaica", "bench-estaciones-meteorologicas", "El EMS necesita contexto meteorológico fiable para clipping, rampas y disponibilidad."),
    ("bench-ems-fotovoltaica", "bench-scada-hibrido-solar-bess", "EMS y SCADA híbrido comparten consignas, eventos de potencia y KPIs operativos."),
    ("bench-ems-fotovoltaica", "bench-mantenimiento-predictivo", "La disponibilidad del EMS depende del estado predictivo de los inversores."),
    ("bench-estaciones-meteorologicas", "bench-calidad-red-ppc", "La meteorología explica curtailment y desviaciones vistas por PPC y calidad de red."),
    ("bench-scada-hibrido-solar-bess", "bench-calidad-red-ppc", "El despacho híbrido impacta directamente en ramp-rate y cumplimiento del PCC."),
    ("bench-mantenimiento-predictivo", "bench-observabilidad-subestaciones", "Los eventos OT y de subestación ayudan a explicar degradación y disparos de inversores."),
    ("bench-parque-eolico-scada", "bench-estaciones-meteorologicas", "El SCADA eólico necesita contexto meteorológico para curva de potencia y yaw."),
    ("bench-parque-eolico-scada", "bench-gestion-curtailment", "El parque eólico es fuente principal de eventos de curtailment por viento."),
    ("bench-calidad-red-ppc", "bench-gestion-curtailment", "Los eventos de calidad de red disparan curtailment y afectan contabilidad de energía perdida."),
    # Software bridges
    ("bench-api-gateway-auth", "bench-react-dashboard", "The gateway authenticates dashboard users and serves as its API backend."),
    ("bench-data-pipeline-etl", "bench-ml-model-serving", "The ETL pipeline produces training data and feature store inputs for ML models."),
    ("bench-api-gateway-auth", "bench-event-driven-microservices", "The gateway routes external requests to internal microservices."),
    ("bench-infra-terraform-k8s", "bench-event-driven-microservices", "Infrastructure provisions and operates the microservices platform."),
    ("bench-mobile-app-flutter", "bench-api-gateway-auth", "The mobile app authenticates via and consumes the API gateway."),
    ("bench-data-pipeline-etl", "bench-event-driven-microservices", "ETL integrates with the event bus for real-time data ingestion."),
]

MANUAL_RELATIONS = [
    # Energy cross-project methodology relations
    {"source_project": "bench-ems-fotovoltaica", "source_key": "shared-methodology", "target_project": "bench-estaciones-meteorologicas", "target_key": "shared-methodology", "relation_type": "supports", "reason": "La metodología meteorológica sustenta el QA/QC que usa el EMS.", "weight": 0.92},
    {"source_project": "bench-ems-fotovoltaica", "source_key": "shared-methodology", "target_project": "bench-scada-hibrido-solar-bess", "target_key": "shared-methodology", "relation_type": "supports", "reason": "EMS y SCADA híbrido comparten la misma disciplina de monitorización.", "weight": 0.90},
    {"source_project": "bench-estaciones-meteorologicas", "source_key": "shared-methodology", "target_project": "bench-calidad-red-ppc", "target_key": "shared-methodology", "relation_type": "applies_to", "reason": "El QA/QC temporal de meteorología se reaplica al cumplimiento del PPC.", "weight": 0.88},
    {"source_project": "bench-mantenimiento-predictivo", "source_key": "shared-methodology", "target_project": "bench-observabilidad-subestaciones", "target_key": "shared-methodology", "relation_type": "derived_from", "reason": "Los modelos predictivos reutilizan la observabilidad OT.", "weight": 0.87},
    {"source_project": "bench-parque-eolico-scada", "source_key": "shared-methodology", "target_project": "bench-estaciones-meteorologicas", "target_key": "shared-methodology", "relation_type": "extends", "reason": "El SCADA eólico depende de datos meteorológicos validados para curva de potencia.", "weight": 0.89},
    {"source_project": "bench-parque-eolico-scada", "source_key": "shared-methodology", "target_project": "bench-gestion-curtailment", "target_key": "shared-methodology", "relation_type": "supports", "reason": "La monitorización eólica alimenta la clasificación y contabilidad de curtailment.", "weight": 0.86},
    {"source_project": "bench-calidad-red-ppc", "source_key": "shared-methodology", "target_project": "bench-gestion-curtailment", "target_key": "shared-methodology", "relation_type": "supports", "reason": "Los eventos de calidad de red disparan curtailment regulatorio.", "weight": 0.88},
    {"source_project": "bench-ems-fotovoltaica", "source_key": "shared-methodology", "target_project": "bench-gestion-curtailment", "target_key": "shared-methodology", "relation_type": "applies_to", "reason": "El EMS aporta el modelo de producción potencial para calcular energía perdida.", "weight": 0.85},
    # Energy cross-project pipeline relations
    {"source_project": "bench-ems-fotovoltaica", "source_key": "shared-pipeline", "target_project": "bench-estaciones-meteorologicas", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "El pipeline EMS consume datos limpios del pipeline meteorológico.", "weight": 0.90},
    {"source_project": "bench-scada-hibrido-solar-bess", "source_key": "shared-pipeline", "target_project": "bench-ems-fotovoltaica", "target_key": "shared-pipeline", "relation_type": "applies_to", "reason": "El pipeline SCADA y el EMS comparten telemetría de inversores y medidores.", "weight": 0.88},
    {"source_project": "bench-calidad-red-ppc", "source_key": "shared-pipeline", "target_project": "bench-observabilidad-subestaciones", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "El pipeline de calidad de red consume eventos OT de subestación.", "weight": 0.87},
    {"source_project": "bench-parque-eolico-scada", "source_key": "shared-pipeline", "target_project": "bench-estaciones-meteorologicas", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "El pipeline eólico consume datos meteorológicos de meteo-torres.", "weight": 0.89},
    {"source_project": "bench-gestion-curtailment", "source_key": "shared-pipeline", "target_project": "bench-calidad-red-ppc", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "El pipeline de curtailment consume eventos de calidad de red del PPC.", "weight": 0.86},
    {"source_project": "bench-mantenimiento-predictivo", "source_key": "shared-pipeline", "target_project": "bench-ems-fotovoltaica", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "El pipeline predictivo consume datos de inversores del pipeline EMS.", "weight": 0.88},
    # Software cross-project relations
    {"source_project": "bench-api-gateway-auth", "source_key": "shared-methodology", "target_project": "bench-react-dashboard", "target_key": "shared-methodology", "relation_type": "supports", "reason": "Gateway auth provides the authentication layer consumed by the dashboard.", "weight": 0.91},
    {"source_project": "bench-api-gateway-auth", "source_key": "shared-methodology", "target_project": "bench-event-driven-microservices", "target_key": "shared-methodology", "relation_type": "supports", "reason": "Gateway routes and authenticates requests to microservices.", "weight": 0.89},
    {"source_project": "bench-data-pipeline-etl", "source_key": "shared-methodology", "target_project": "bench-ml-model-serving", "target_key": "shared-methodology", "relation_type": "supports", "reason": "ETL pipeline produces clean data consumed by ML training and feature store.", "weight": 0.90},
    {"source_project": "bench-data-pipeline-etl", "source_key": "shared-methodology", "target_project": "bench-event-driven-microservices", "target_key": "shared-methodology", "relation_type": "applies_to", "reason": "ETL and microservices share Kafka infrastructure and schema conventions.", "weight": 0.87},
    {"source_project": "bench-infra-terraform-k8s", "source_key": "shared-methodology", "target_project": "bench-event-driven-microservices", "target_key": "shared-methodology", "relation_type": "supports", "reason": "Infrastructure provides the K8s platform where microservices run.", "weight": 0.88},
    {"source_project": "bench-mobile-app-flutter", "source_key": "shared-methodology", "target_project": "bench-api-gateway-auth", "target_key": "shared-methodology", "relation_type": "extends", "reason": "Mobile app depends on gateway for authentication and API access.", "weight": 0.90},
    {"source_project": "bench-infra-terraform-k8s", "source_key": "shared-methodology", "target_project": "bench-ml-model-serving", "target_key": "shared-methodology", "relation_type": "supports", "reason": "Infrastructure manages K8s clusters where ML models are served.", "weight": 0.86},
    # Software pipeline relations
    {"source_project": "bench-api-gateway-auth", "source_key": "shared-pipeline", "target_project": "bench-react-dashboard", "target_key": "shared-pipeline", "relation_type": "same_concept", "reason": "Both use the same CI/CD pipeline pattern with lint, test, build, deploy.", "weight": 0.85},
    {"source_project": "bench-data-pipeline-etl", "source_key": "shared-pipeline", "target_project": "bench-ml-model-serving", "target_key": "shared-pipeline", "relation_type": "applies_to", "reason": "ETL CI validates data schemas, ML CI validates model quality — complementary.", "weight": 0.84},
    {"source_project": "bench-infra-terraform-k8s", "source_key": "shared-pipeline", "target_project": "bench-api-gateway-auth", "target_key": "shared-pipeline", "relation_type": "supports", "reason": "Infra CI/CD provides the deployment target for gateway releases.", "weight": 0.87},
    {"source_project": "bench-infra-terraform-k8s", "source_key": "shared-pipeline", "target_project": "bench-event-driven-microservices", "target_key": "shared-pipeline", "relation_type": "supports", "reason": "Infra pipeline provisions the microservices platform and ArgoCD reconciles.", "weight": 0.86},
    {"source_project": "bench-mobile-app-flutter", "source_key": "shared-pipeline", "target_project": "bench-api-gateway-auth", "target_key": "shared-pipeline", "relation_type": "extends", "reason": "Mobile CI generates API client from gateway OpenAPI spec.", "weight": 0.83},
    # Cross-domain relations (energy ↔ software)
    {"source_project": "bench-data-pipeline-etl", "source_key": "shared-methodology", "target_project": "bench-ems-fotovoltaica", "target_key": "shared-pipeline", "relation_type": "same_concept", "reason": "Both implement telemetry ingestion with quality checks, different domains.", "weight": 0.82},
    {"source_project": "bench-infra-terraform-k8s", "source_key": "shared-pipeline", "target_project": "bench-scada-hibrido-solar-bess", "target_key": "shared-pipeline", "relation_type": "applies_to", "reason": "Containerized deployment patterns from infra apply to SCADA modernization.", "weight": 0.78},
    {"source_project": "bench-event-driven-microservices", "source_key": "shared-methodology", "target_project": "bench-gestion-curtailment", "target_key": "shared-pipeline", "relation_type": "same_concept", "reason": "Event-driven patterns in microservices mirror event processing in curtailment management.", "weight": 0.80},
    {"source_project": "bench-react-dashboard", "source_key": "shared-methodology", "target_project": "bench-ems-fotovoltaica", "target_key": "shared-methodology", "relation_type": "applies_to", "reason": "Dashboard visualization patterns apply to EMS operational views.", "weight": 0.79},
    {"source_project": "bench-ml-model-serving", "source_key": "shared-methodology", "target_project": "bench-mantenimiento-predictivo", "target_key": "shared-methodology", "relation_type": "supports", "reason": "ML serving infrastructure supports predictive maintenance model deployment.", "weight": 0.84},
]


# ═══════════════════════════════════════════════════════════════════
# CATALOG BUILDER
# ═══════════════════════════════════════════════════════════════════

def _namespaced_project(namespace: str, slug: str) -> str:
    normalized = namespace.strip().strip("-")
    if not normalized:
        return slug
    return f"{normalized}-{slug}"


def _session_id(namespace: str, slug: str) -> str:
    normalized = namespace.strip().strip("-")
    if not normalized:
        return f"session-{slug}"
    return f"session-{normalized}-{slug}"


def build_benchmark_catalog(namespace: str = "") -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    for definition in PROJECT_CATALOG:
        project_entry = deepcopy(definition)
        project_entry["project"] = _namespaced_project(namespace, definition["slug"])
        project_entry["session"]["session_id"] = _session_id(namespace, definition["slug"])
        projects.append(project_entry)

    bridges = [
        {
            "project": _namespaced_project(namespace, left),
            "related_project": _namespaced_project(namespace, right),
            "reason": reason,
            "active": True,
            "created_by": "bench-seed",
        }
        for left, right, reason in PROJECT_BRIDGES
    ]

    manual_relations = []
    for relation in MANUAL_RELATIONS:
        relation_entry = deepcopy(relation)
        relation_entry["source_project"] = _namespaced_project(namespace, relation["source_project"])
        relation_entry["target_project"] = _namespaced_project(namespace, relation["target_project"])
        manual_relations.append(relation_entry)

    return {
        "namespace": namespace.strip().strip("-"),
        "projects": projects,
        "bridges": bridges,
        "manual_relations": manual_relations,
        "shared_method_query": SHARED_METHOD_QUERY,
        "test_now": BENCHMARK_TEST_NOW,
    }


def expected_project_names(namespace: str = "") -> list[str]:
    return [_namespaced_project(namespace, definition["slug"]) for definition in PROJECT_CATALOG]
