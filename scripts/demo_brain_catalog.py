from __future__ import annotations

from copy import deepcopy
from typing import Any


DEMO_TEST_NOW = "2030-01-01T00:00:00+00:00"
SHARED_METHOD_QUERY = (
    "condition monitoring quality control de series temporales anomaly detection "
    "telemetría operacional industrial"
)

COMMON_METHOD_PREFIX = (
    "Metodología común de monitorización industrial basada en condition monitoring, "
    "quality control de series temporales y anomaly detection sobre telemetría operacional."
)
COMMON_PIPELINE_PREFIX = (
    "Pipeline común de telemetría industrial con gateway edge, normalización de protocolos, "
    "timestamp unificado y control de calidad antes del historiado."
)

SHARED_TAGS = {
    "method_condition": "method/condition-monitoring",
    "method_quality": "method/time-series-quality-control",
    "method_anomaly": "method/anomaly-detection",
    "stack_pipeline": "stack/telemetry-pipeline",
    "protocol_modbus": "protocol/modbus",
    "protocol_iec104": "protocol/iec-104",
    "metric_availability": "metric/availability",
    "metric_power_quality": "metric/power-quality",
}


PROJECT_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "demo-ems-fotovoltaica",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.98,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["metric_availability"],
                    "domain/ems",
                    "asset/fotovoltaica",
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En el EMS fotovoltaico esta metodología se usa para "
                    "correlacionar irradiancia, consignas del PPC, clipping, alarmas por bloque y "
                    "disponibilidad por inversor."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.94,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["protocol_iec104"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/ems",
                    "asset/fotovoltaica",
                    "stack/ppc",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En la planta fotovoltaica el pipeline EMS unifica "
                    "telemetría de inversores, PPC, contador fiscal y estación meteo para controlar "
                    "rampas, cos phi y curtailment."
                ),
            },
            {
                "key": "ppc-weather-correlation",
                "memory_type": "general",
                "importance": 0.88,
                "tags": [
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/ems",
                    "domain/meteorologia",
                    "stack/ppc",
                ],
                "content": (
                    "El EMS fotovoltaico cruza irradiancia, temperatura de módulo y consignas del PPC "
                    "para explicar clipping, ramp-rate events y recortes preventivos por calidad de red."
                ),
            },
            {
                "key": "availability-kpis",
                "memory_type": "general",
                "importance": 0.84,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    SHARED_TAGS["method_anomaly"],
                    "domain/ems",
                    "asset/inversores",
                ],
                "content": (
                    "Los KPI de disponibilidad del EMS separan indisponibilidad por inversor, tracker, "
                    "SCB y comunicaciones para priorizar incidencias con mayor impacto energético."
                ),
            },
        ],
        "decision": {
            "title": "Muestreo unificado a 1 minuto para EMS fotovoltaico",
            "decision": (
                "Se normaliza la telemetría del EMS y del PPC a un paso de 1 minuto antes del "
                "historiado operativo y de los cálculos de cumplimiento."
            ),
            "rationale": (
                "La resolución común reduce desfases entre consignas, meteorología y medidas de red "
                "cuando se analizan clipping, rampas y disponibilidad."
            ),
            "alternatives": (
                "Mantener tasas distintas por dispositivo y reconciliar offline elevaba la complejidad "
                "y degradaba la trazabilidad."
            ),
            "tags": [
                SHARED_TAGS["stack_pipeline"],
                SHARED_TAGS["protocol_modbus"],
                "domain/ems",
                "stack/ppc",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "ems-reactiva-signo-invertido",
            "error_description": (
                "El signo de potencia reactiva quedó invertido entre EMS y PPC y el sistema aplicó "
                "consignas erróneas en el punto de conexión."
            ),
            "solution": (
                "Se fijó una tabla de normalización de signo por fabricante y una comprobación diaria "
                "contra el analizador de red del PCC."
            ),
            "tags": [
                SHARED_TAGS["metric_power_quality"],
                SHARED_TAGS["protocol_modbus"],
                "domain/ems",
                "stack/ppc",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Alinear EMS, PPC y meteorología de planta fotovoltaica",
            "outcome": "Quedó establecida una lectura común de disponibilidad, clipping y reactiva.",
            "summary": (
                "La sesión consolidó una metodología común de monitorización industrial para EMS "
                "fotovoltaico, con condition monitoring, QA/QC temporal y anomaly detection sobre "
                "telemetría del PPC, inversores y estación meteo."
            ),
            "changes": [
                "Se unificó el pipeline de telemetría del EMS y del PPC a resolución de 1 minuto.",
                "Se añadió correlación entre irradiancia, clipping y cumplimiento de rampas.",
            ],
            "decisions": [
                {
                    "title": "Normalizar el paso temporal del EMS",
                    "decision": "Adoptar 1 minuto como granularidad operativa común.",
                    "rationale": "Permite comparar consignas, meteorología y red sin desfases.",
                }
            ],
            "errors": [
                {
                    "error_signature": "ems-reactiva-signo-invertido",
                    "description": "Signo invertido de reactiva entre EMS y PPC.",
                    "solution": "Normalización por fabricante y validación diaria contra PCC.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Extender detección de clipping por bloque",
                    "state": "pending",
                    "details": "Agregar correlación por tracker y SCB.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                SHARED_TAGS["stack_pipeline"],
                "domain/ems",
                "asset/fotovoltaica",
            ],
        },
    },
    {
        "slug": "demo-monitorizacion-estaciones-meteorologicas",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.98,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["stack_pipeline"],
                    "domain/meteorologia",
                    "asset/estaciones-meteo",
                    SHARED_TAGS["metric_availability"],
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En la monitorización de estaciones meteorológicas se "
                    "usa para validar irradiancia, temperatura ambiente, viento, humedad y drift de "
                    "sensores antes de publicar KPI operativos."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.92,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["metric_availability"],
                    "domain/meteorologia",
                    "asset/estaciones-meteo",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En las estaciones meteorológicas el pipeline integra "
                    "dataloggers, gateways Modbus y reglas de QA/QC para irradiancia, temperatura y "
                    "viento antes de exponer series limpias al resto de sistemas."
                ),
            },
            {
                "key": "sensor-drift-correlation",
                "memory_type": "general",
                "importance": 0.87,
                "tags": [
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    "domain/meteorologia",
                    "asset/estaciones-meteo",
                    "metric/irradiance-quality",
                ],
                "content": (
                    "La correlación entre piranómetro, célula de referencia y satélite permite "
                    "detectar drift, sombras parciales y suciedad persistente en estaciones meteo."
                ),
            },
            {
                "key": "gateway-availability",
                "memory_type": "general",
                "importance": 0.83,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    SHARED_TAGS["protocol_modbus"],
                    "domain/meteorologia",
                    "stack/gateway-edge",
                ],
                "content": (
                    "La disponibilidad de la estación meteorológica se calcula separando fallos de "
                    "sensor, pérdida de gateway, latencia satelital y huecos por mantenimiento."
                ),
            },
        ],
        "decision": {
            "title": "Validación cruzada entre piranómetro y referencia satelital",
            "decision": (
                "Las reglas de plausibilidad meteorológica combinan sensor de campo y referencia "
                "externa antes de aceptar irradiancia como dato operativo."
            ),
            "rationale": (
                "Reduce falsas conclusiones sobre suciedad o clipping cuando un solo sensor deriva."
            ),
            "alternatives": "Usar solo umbrales físicos dejaba pasar drift lento y offsets persistentes.",
            "tags": [
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                "domain/meteorologia",
                "asset/estaciones-meteo",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "meteo-piranometro-sombreado",
            "error_description": (
                "El piranómetro principal quedó parcialmente sombreado y el pipeline aceptó irradiancia "
                "baja como si fuera una nube real."
            ),
            "solution": (
                "Se añadió una comparación obligatoria con célula de referencia y un detector de "
                "asimetría diurna para descartar sombras locales."
            ),
            "tags": [
                SHARED_TAGS["method_quality"],
                "domain/meteorologia",
                "asset/estaciones-meteo",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Mejorar QA/QC de estaciones meteorológicas en activos renovables",
            "outcome": "Quedó operativa una metodología común de validación de sensores y disponibilidad.",
            "summary": (
                "La sesión consolidó el uso de condition monitoring, QA/QC temporal y anomaly detection "
                "para evaluar estaciones meteorológicas, detectar drift y compartir telemetría fiable "
                "con EMS, PPC y mantenimiento predictivo."
            ),
            "changes": [
                "Se añadió validación cruzada con referencia satelital.",
                "Se separó disponibilidad por sensor, gateway y comunicaciones.",
            ],
            "decisions": [
                {
                    "title": "Cruzar irradiancia de campo con referencia externa",
                    "decision": "Un dato crítico no se acepta sin al menos dos fuentes coherentes.",
                    "rationale": "Evita propagar sensores degradados al resto del cerebro.",
                }
            ],
            "errors": [
                {
                    "error_signature": "meteo-piranometro-sombreado",
                    "description": "Sombra parcial sobre piranómetro principal.",
                    "solution": "Cruce con célula de referencia y detector de asimetría diurna.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Añadir detección de calentador de anemómetro atascado",
                    "state": "pending",
                    "details": "Extender reglas para campañas invernales.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                "domain/meteorologia",
                "asset/estaciones-meteo",
            ],
        },
    },
    {
        "slug": "demo-scada-hibrido-solar-bess",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.97,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["stack_pipeline"],
                    "domain/scada",
                    "asset/bess",
                    SHARED_TAGS["metric_availability"],
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En el SCADA híbrido solar+BESS esta metodología se usa "
                    "para coordinar SoC, consignas de despacho, alarmas de potencia y disponibilidad "
                    "de convertidores de batería e inversores solares."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.92,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["protocol_iec104"],
                    "domain/scada",
                    "asset/bess",
                    "asset/fotovoltaica",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En el SCADA híbrido se unifica telemetría de BESS, "
                    "inversores solares y medidores de red para explicar rampas, SoC útil y eventos de "
                    "limitación operativa."
                ),
            },
            {
                "key": "dispatch-ramp-control",
                "memory_type": "general",
                "importance": 0.89,
                "tags": [
                    SHARED_TAGS["metric_power_quality"],
                    SHARED_TAGS["method_anomaly"],
                    "domain/scada",
                    "asset/bess",
                    "stack/dispatch",
                ],
                "content": (
                    "El control híbrido prioriza ramp-rate compliance y estado de carga estable antes "
                    "de perseguir consignas agresivas del mercado o del despacho centralizado."
                ),
            },
            {
                "key": "bess-availability-kpis",
                "memory_type": "general",
                "importance": 0.84,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    "domain/scada",
                    "asset/bess",
                    "asset/inversores",
                ],
                "content": (
                    "La disponibilidad híbrida separa indisponibilidad del BESS, limitación del PCS y "
                    "bloqueos del SCADA para no atribuir toda la pérdida al activo solar."
                ),
            },
        ],
        "decision": {
            "title": "Priorizar ramp-rate compliance en el SCADA híbrido",
            "decision": (
                "El SCADA solar+BESS antepone cumplimiento de rampa y estabilidad del SoC a consignas "
                "agresivas cuando ambas metas entran en conflicto."
            ),
            "rationale": (
                "Evita oscilaciones de consignas y reduce estrés térmico en PCS e inversores."
            ),
            "alternatives": "Forzar el setpoint nominal generaba más eventos de limitación y alarmas.",
            "tags": [
                SHARED_TAGS["metric_power_quality"],
                SHARED_TAGS["method_anomaly"],
                "domain/scada",
                "asset/bess",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "scada-bess-desfase-timestamps",
            "error_description": (
                "El BESS publicaba timestamps con desfase y el SCADA interpretó transferencias de "
                "potencia fuera de secuencia."
            ),
            "solution": (
                "Se añadió sincronización NTP obligatoria y descarte de paquetes con deriva temporal "
                "superior a dos segundos."
            ),
            "tags": [
                SHARED_TAGS["stack_pipeline"],
                "domain/scada",
                "asset/bess",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Estabilizar un cerebro operativo para SCADA híbrido solar+BESS",
            "outcome": "El dataset quedó enlazado con EMS, PPC y mantenimiento predictivo.",
            "summary": (
                "La sesión consolidó metodología compartida, pipeline común y criterios de despacho "
                "para el SCADA híbrido solar+BESS, reforzando relaciones con EMS, calidad de red y "
                "observabilidad OT."
            ),
            "changes": [
                "Se normalizó telemetría de PCS, inversores y medidores de red.",
                "Se reforzó la lectura conjunta de ramp-rate, SoC y disponibilidad híbrida.",
            ],
            "decisions": [
                {
                    "title": "Rampa primero, setpoint después",
                    "decision": "El control híbrido conserva compliance de rampa como prioridad.",
                    "rationale": "Minimiza oscilaciones y eventos evitables.",
                }
            ],
            "errors": [
                {
                    "error_signature": "scada-bess-desfase-timestamps",
                    "description": "Desfase temporal entre BESS y solar.",
                    "solution": "Sincronización NTP y descarte de paquetes fuera de ventana.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Correlacionar alarmas PCS con temperatura ambiente",
                    "state": "pending",
                    "details": "Añadir contexto meteo al diagnóstico híbrido.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                SHARED_TAGS["stack_pipeline"],
                "domain/scada",
                "asset/bess",
            ],
        },
    },
    {
        "slug": "demo-calidad-de-red-y-ppc",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.97,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["metric_power_quality"],
                    SHARED_TAGS["stack_pipeline"],
                    "domain/power-quality",
                    "stack/ppc",
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En calidad de red y PPC se usa para correlacionar huecos, "
                    "THD, flicker, consignas de reactiva y disponibilidad del punto de conexión."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.91,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_iec104"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/power-quality",
                    "stack/ppc",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En el PPC y en el analizador de red se unifican "
                    "medidas IEC-104, Modbus y eventos de compliance para explicar desvíos en el PCC."
                ),
            },
            {
                "key": "harmonic-events",
                "memory_type": "general",
                "importance": 0.89,
                "tags": [
                    SHARED_TAGS["metric_power_quality"],
                    SHARED_TAGS["method_quality"],
                    "domain/power-quality",
                    "stack/ppc",
                    "asset/pcc",
                ],
                "content": (
                    "El cerebro de calidad de red separa THD, flicker y desequilibrio por ventana "
                    "temporal para distinguir eventos reales del PCC de ruido de medida o resampling."
                ),
            },
            {
                "key": "compliance-kpis",
                "memory_type": "general",
                "importance": 0.84,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/power-quality",
                    "stack/ppc",
                ],
                "content": (
                    "Los KPI del PPC combinan disponibilidad del controlador, cumplimiento de reactiva "
                    "y calidad de red para no mezclar indisponibilidad operativa con eventos de red."
                ),
            },
        ],
        "decision": {
            "title": "Separar ventanas lenta y rápida para eventos de calidad de red",
            "decision": (
                "Los eventos del PCC se calculan con una ventana rápida para detección y otra lenta "
                "para consolidación de cumplimiento."
            ),
            "rationale": (
                "Reduce falsos positivos de armónicos y permite explicar eventos breves sin perder "
                "trazabilidad en informes de compliance."
            ),
            "alternatives": "Una única ventana temporal mezclaba ruido transitorio con eventos persistentes.",
            "tags": [
                SHARED_TAGS["metric_power_quality"],
                SHARED_TAGS["method_quality"],
                "domain/power-quality",
                "stack/ppc",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "ppc-armonicos-ventana-incorrecta",
            "error_description": (
                "El cálculo de armónicos del PPC se hizo con una ventana incorrecta y generó alarmas "
                "de THD inexistentes en el PCC."
            ),
            "solution": (
                "Se alineó la ventana con el analizador de red y se bloquearon comparaciones con "
                "resampling inconsistente."
            ),
            "tags": [
                SHARED_TAGS["metric_power_quality"],
                SHARED_TAGS["method_quality"],
                "domain/power-quality",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Integrar calidad de red y PPC en el cerebro industrial",
            "outcome": "Quedó trazada la conexión entre compliance, telemetría y metodología compartida.",
            "summary": (
                "La sesión consolidó cómo el cerebro interpreta calidad de red y PPC con metodología "
                "compartida, pipeline común y KPI coherentes con EMS, SCADA híbrido y observabilidad OT."
            ),
            "changes": [
                "Se normalizaron eventos IEC-104 y medidas Modbus del PCC.",
                "Se separó detección rápida y consolidación lenta para compliance.",
            ],
            "decisions": [
                {
                    "title": "Dos ventanas para calidad de red",
                    "decision": "Separar detección y consolidación de eventos del PCC.",
                    "rationale": "Evita falsos positivos y mejora trazabilidad.",
                }
            ],
            "errors": [
                {
                    "error_signature": "ppc-armonicos-ventana-incorrecta",
                    "description": "THD falso por ventana de cálculo incorrecta.",
                    "solution": "Alinear ventana y resampling con el analizador de red.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Correlacionar huecos de tensión con breaker upstream",
                    "state": "pending",
                    "details": "Cruzar PCC con telemetría OT de subestación.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                SHARED_TAGS["metric_power_quality"],
                "domain/power-quality",
            ],
        },
    },
    {
        "slug": "demo-mantenimiento-predictivo-inversores",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.97,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["metric_availability"],
                    "domain/predictive-maintenance",
                    "asset/inversores",
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En mantenimiento predictivo de inversores esta metodología "
                    "se usa para vigilar IGBT, ventiladores, corrientes por MPPT y temperatura "
                    "ambiente antes de que aparezca indisponibilidad."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.91,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["metric_availability"],
                    "domain/predictive-maintenance",
                    "asset/inversores",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En mantenimiento predictivo el pipeline recoge alarmas, "
                    "temperaturas y corrientes de inversor para construir residuales térmicos y "
                    "diagnósticos por familia de equipo."
                ),
            },
            {
                "key": "thermal-residuals",
                "memory_type": "general",
                "importance": 0.89,
                "tags": [
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["method_condition"],
                    "domain/predictive-maintenance",
                    "asset/inversores",
                    "metric/thermal-health",
                ],
                "content": (
                    "Los residuales térmicos por familia de inversor detectan degradación de "
                    "ventiladores y IGBT antes de que la potencia disponible caiga de forma visible."
                ),
            },
            {
                "key": "mtbf-availability",
                "memory_type": "general",
                "importance": 0.84,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    "domain/predictive-maintenance",
                    "asset/inversores",
                    "metric/mtbf",
                ],
                "content": (
                    "La visión predictiva separa disponibilidad energética, tiempo medio entre fallos "
                    "y degradación paulatina para priorizar mantenimiento antes de un disparo duro."
                ),
            },
        ],
        "decision": {
            "title": "Usar residuales térmicos por familia de inversor",
            "decision": (
                "El mantenimiento predictivo agrupa inversores por familia eléctrica y calcula "
                "residuales térmicos antes de disparar alertas de degradación."
            ),
            "rationale": (
                "Comparar equipos equivalentes reduce falsos positivos por clima o consigna operativa."
            ),
            "alternatives": "Umbrales fijos por temperatura no diferenciaban operación intensa de degradación.",
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_anomaly"],
                "domain/predictive-maintenance",
                "asset/inversores",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "predictivo-termistor-desplazado",
            "error_description": (
                "Un termistor desplazado generó alarmas térmicas falsas y el modelo predictivo "
                "marcó varios inversores como degradados sin estarlo."
            ),
            "solution": (
                "Se comparó con temperatura de carcasa y potencia despachada para invalidar sensores "
                "fuera de rango físico."
            ),
            "tags": [
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                "domain/predictive-maintenance",
                "asset/inversores",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Conectar mantenimiento predictivo de inversores con el resto del cerebro",
            "outcome": "Quedó trazada la relación con EMS, estaciones meteo y observabilidad OT.",
            "summary": (
                "La sesión reforzó el uso de condition monitoring, anomaly detection y pipeline común "
                "para mantenimiento predictivo de inversores, con impacto directo en disponibilidad y "
                "telemetría compartida con EMS y subestaciones."
            ),
            "changes": [
                "Se añadieron residuales térmicos por familia de inversor.",
                "Se conectó indisponibilidad energética con señales predictivas y contexto OT.",
            ],
            "decisions": [
                {
                    "title": "Agrupar por familia eléctrica",
                    "decision": "Las alertas predictivas se calculan entre equipos equivalentes.",
                    "rationale": "Disminuye falsos positivos por operación desigual.",
                }
            ],
            "errors": [
                {
                    "error_signature": "predictivo-termistor-desplazado",
                    "description": "Termistor desplazado y falsas alarmas térmicas.",
                    "solution": "Cruce con carcasa, potencia y validación física.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Cruzar fallos térmicos con calidad de red",
                    "state": "pending",
                    "details": "Buscar relación con eventos del PCC y transformador.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                SHARED_TAGS["metric_availability"],
                "domain/predictive-maintenance",
                "asset/inversores",
            ],
        },
    },
    {
        "slug": "demo-observabilidad-subestaciones-y-ot",
        "memories": [
            {
                "key": "shared-methodology",
                "memory_type": "architecture",
                "importance": 0.97,
                "tags": [
                    SHARED_TAGS["method_condition"],
                    SHARED_TAGS["method_quality"],
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_iec104"],
                    "domain/ot",
                    "asset/subestacion",
                ],
                "content": (
                    f"{COMMON_METHOD_PREFIX} En observabilidad de subestaciones y OT se usa para "
                    "seguir breaker status, corriente por bahía, temperatura de transformador y "
                    "señales IEC-104 antes de que se propaguen al resto de activos."
                ),
            },
            {
                "key": "shared-pipeline",
                "memory_type": "architecture",
                "importance": 0.92,
                "tags": [
                    SHARED_TAGS["stack_pipeline"],
                    SHARED_TAGS["protocol_iec104"],
                    SHARED_TAGS["protocol_modbus"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/ot",
                    "asset/subestacion",
                ],
                "content": (
                    f"{COMMON_PIPELINE_PREFIX} En subestaciones y OT el pipeline normaliza IEC-104, "
                    "alarmas de RTU y medidas de transformador antes de cruzarlas con eventos del PCC "
                    "y del sistema energético."
                ),
            },
            {
                "key": "breaker-transformer-correlation",
                "memory_type": "general",
                "importance": 0.88,
                "tags": [
                    SHARED_TAGS["method_anomaly"],
                    SHARED_TAGS["protocol_iec104"],
                    "domain/ot",
                    "asset/subestacion",
                    "asset/transformador",
                ],
                "content": (
                    "La observabilidad OT correlaciona aperturas de breaker, carga de transformador y "
                    "alarmas de protección para explicar huecos, disparos y pérdidas de disponibilidad."
                ),
            },
            {
                "key": "ot-availability-kpis",
                "memory_type": "general",
                "importance": 0.84,
                "tags": [
                    SHARED_TAGS["metric_availability"],
                    SHARED_TAGS["metric_power_quality"],
                    "domain/ot",
                    "asset/subestacion",
                ],
                "content": (
                    "Los KPI OT separan indisponibilidad por comunicaciones, por RTU y por equipo de "
                    "patio para que la causa raíz no se diluya en la operación de planta."
                ),
            },
        ],
        "decision": {
            "title": "Normalizar IEC-104 antes del enriquecimiento OT",
            "decision": (
                "Toda señal IEC-104 se normaliza y timestampa antes de mezclarse con contexto de "
                "protecciones, transformadores y eventos de red."
            ),
            "rationale": (
                "Sin una base temporal estable, la correlación OT con PPC y EMS pierde trazabilidad."
            ),
            "alternatives": "Enriquecer antes de normalizar generaba secuencias incoherentes entre sistemas.",
            "tags": [
                SHARED_TAGS["protocol_iec104"],
                SHARED_TAGS["stack_pipeline"],
                "domain/ot",
                "asset/subestacion",
            ],
            "agent_id": "demo-seed",
        },
        "error": {
            "error_signature": "ot-spontaneous-flood",
            "error_description": (
                "Una RTU OT envió una avalancha de spontaneous events sin calidad válida y saturó la "
                "cadena de alarmas aguas arriba."
            ),
            "solution": (
                "Se añadió validación de calidad IEC-104, deduplicación por secuencia y límite por "
                "ventana temporal antes del enriquecimiento."
            ),
            "tags": [
                SHARED_TAGS["protocol_iec104"],
                SHARED_TAGS["method_quality"],
                "domain/ot",
                "asset/subestacion",
            ],
        },
        "session": {
            "agent_id": "demo-seed",
            "goal": "Conectar subestaciones y OT con el cerebro energético",
            "outcome": "Quedó integrada la capa OT con calidad de red, EMS y mantenimiento.",
            "summary": (
                "La sesión conectó observabilidad OT con metodología compartida, pipeline común y "
                "eventos de red para explicar disparos, huecos y degradaciones de disponibilidad."
            ),
            "changes": [
                "Se normalizaron señales IEC-104 y medidas de transformador.",
                "Se enlazaron eventos OT con calidad de red y mantenimiento predictivo.",
            ],
            "decisions": [
                {
                    "title": "Normalizar IEC-104 primero",
                    "decision": "Toda señal OT se limpia y timestampa antes de enriquecerla.",
                    "rationale": "Evita secuencias incoherentes entre RTU y analítica.",
                }
            ],
            "errors": [
                {
                    "error_signature": "ot-spontaneous-flood",
                    "description": "Avalancha de spontaneous events sin calidad válida.",
                    "solution": "Validación IEC-104 y deduplicación por secuencia.",
                }
            ],
            "follow_ups": [
                {
                    "title": "Cruzar alarmas de bahía con disponibilidad EMS",
                    "state": "pending",
                    "details": "Añadir correlación automática entre OT y operación energética.",
                }
            ],
            "tags": [
                SHARED_TAGS["method_condition"],
                SHARED_TAGS["method_quality"],
                SHARED_TAGS["method_anomaly"],
                SHARED_TAGS["stack_pipeline"],
                SHARED_TAGS["protocol_iec104"],
                "domain/ot",
            ],
        },
    },
]

PROJECT_BRIDGES = [
    (
        "demo-ems-fotovoltaica",
        "demo-monitorizacion-estaciones-meteorologicas",
        "El EMS necesita contexto meteorológico fiable para clipping, rampas y disponibilidad.",
    ),
    (
        "demo-ems-fotovoltaica",
        "demo-scada-hibrido-solar-bess",
        "El EMS y el SCADA híbrido comparten consignas, eventos de potencia y KPIs operativos.",
    ),
    (
        "demo-ems-fotovoltaica",
        "demo-mantenimiento-predictivo-inversores",
        "La disponibilidad del EMS depende del estado predictivo de los inversores.",
    ),
    (
        "demo-monitorizacion-estaciones-meteorologicas",
        "demo-calidad-de-red-y-ppc",
        "La meteorología explica curtailment y desviaciones vistas por PPC y calidad de red.",
    ),
    (
        "demo-scada-hibrido-solar-bess",
        "demo-calidad-de-red-y-ppc",
        "El despacho híbrido impacta directamente en ramp-rate y cumplimiento del PCC.",
    ),
    (
        "demo-mantenimiento-predictivo-inversores",
        "demo-observabilidad-subestaciones-y-ot",
        "Los eventos OT y de subestación ayudan a explicar degradación y disparos de inversores.",
    ),
]

MANUAL_RELATIONS = [
    {
        "source_project": "demo-ems-fotovoltaica",
        "source_key": "shared-methodology",
        "target_project": "demo-monitorizacion-estaciones-meteorologicas",
        "target_key": "shared-methodology",
        "relation_type": "supports",
        "reason": "La metodología meteorológica sustenta el QA/QC que usa el EMS.",
        "weight": 0.92,
    },
    {
        "source_project": "demo-ems-fotovoltaica",
        "source_key": "shared-methodology",
        "target_project": "demo-scada-hibrido-solar-bess",
        "target_key": "shared-methodology",
        "relation_type": "supports",
        "reason": "EMS y SCADA híbrido comparten la misma disciplina de monitorización industrial.",
        "weight": 0.9,
    },
    {
        "source_project": "demo-monitorizacion-estaciones-meteorologicas",
        "source_key": "shared-methodology",
        "target_project": "demo-calidad-de-red-y-ppc",
        "target_key": "shared-methodology",
        "relation_type": "applies_to",
        "reason": "El QA/QC temporal de meteorología se reaplica al cumplimiento del PPC y del PCC.",
        "weight": 0.88,
    },
    {
        "source_project": "demo-mantenimiento-predictivo-inversores",
        "source_key": "shared-methodology",
        "target_project": "demo-observabilidad-subestaciones-y-ot",
        "target_key": "shared-methodology",
        "relation_type": "derived_from",
        "reason": "Los modelos predictivos reutilizan la observabilidad OT para explicar disparos y degradación.",
        "weight": 0.87,
    },
]


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


def build_demo_catalog(namespace: str = "") -> dict[str, Any]:
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
            "created_by": "demo-seed",
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
        "test_now": DEMO_TEST_NOW,
    }


def expected_project_names(namespace: str = "") -> list[str]:
    return [_namespaced_project(namespace, definition["slug"]) for definition in PROJECT_CATALOG]
