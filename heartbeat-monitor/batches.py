"""Trap batch definitions for heartbeat monitor.

Each batch is designed to provoke specific biological processes.
Content uses the photovoltaic/SCADA/industrial domain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrapMemory:
    content: str
    memory_type: str
    tags: str
    importance: float = 0.8


@dataclass
class TrapBatch:
    name: str
    description: str
    memories: list[TrapMemory]
    provokes: str


@dataclass
class CycleContext:
    """Mutable state for a single heartbeat cycle."""
    cycle_id: str = field(default_factory=lambda: f"hb-cycle-{uuid.uuid4().hex[:8]}")
    project_a: str = ""
    project_b: str = ""
    memory_ids: dict[str, str] = field(default_factory=dict)
    initial_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    post_sleep_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_projects(self, prefix: str) -> None:
        tag = uuid.uuid4().hex[:6]
        self.project_a = f"heartbeat-{prefix}-{tag}"
        self.project_b = f"heartbeat-{prefix}-cross-{tag}"


BATCH_1_CLUSTER = TrapBatch(
    name="cluster_base",
    description="3 related inverter monitoring memories to form a cluster",
    provokes="relationship formation, synapse tiers 1-2, keyphrase extraction",
    memories=[
        TrapMemory(
            content="La monitorización de inversores fotovoltaicos requiere lectura de registros Modbus TCP cada 10 segundos para detectar fallos de string",
            memory_type="architecture",
            tags="inversores,modbus,monitorizacion",
            importance=0.85,
        ),
        TrapMemory(
            content="Decidimos usar polling síncrono para la lectura de inversores porque el firmware no soporta notificaciones push",
            memory_type="decision",
            tags="inversores,polling,firmware",
            importance=0.8,
        ),
        TrapMemory(
            content="Los inversores Huawei SUN2000 reportan potencia activa en el registro 32080 con factor de escala 1000",
            memory_type="observation",
            tags="inversores,huawei,registros",
            importance=0.75,
        ),
    ],
)

BATCH_2_CONTRADICTION = TrapBatch(
    name="contradiction",
    description="2 contradictory decisions about SCADA polling strategy",
    provokes="contradiction detection, negation patterns, contradiction queue",
    memories=[
        TrapMemory(
            content="Usar polling SCADA cada 5 segundos es la mejor práctica para monitorización en tiempo real de inversores",
            memory_type="decision",
            tags="scada,polling,inversores",
            importance=0.85,
        ),
        TrapMemory(
            content="No usar polling SCADA, implementar arquitectura event-driven con MQTT porque el polling cada 5 segundos satura el bus de comunicaciones",
            memory_type="decision",
            tags="scada,polling,mqtt,inversores",
            importance=0.85,
        ),
    ],
)

BATCH_3_CROSS_PROJECT = TrapBatch(
    name="cross_project",
    description="2 memories in a second project with bridge to first",
    provokes="cross-project bridge, permeability scoring, cross-project myelin",
    memories=[
        TrapMemory(
            content="El sistema de mantenimiento predictivo usa los mismos registros Modbus de inversores para calcular degradación de paneles",
            memory_type="architecture",
            tags="mantenimiento-predictivo,modbus,inversores",
            importance=0.85,
        ),
        TrapMemory(
            content="La correlación entre temperatura de módulo y potencia de salida permite predecir fallos antes de que ocurran",
            memory_type="observation",
            tags="mantenimiento-predictivo,temperatura,prediccion",
            importance=0.8,
        ),
    ],
)

BATCH_5_COLD = TrapBatch(
    name="cold_memory",
    description="1 memory that will never be accessed — decay target",
    provokes="Ebbinghaus decay in REM phase, stability reduction",
    memories=[
        TrapMemory(
            content="El protocolo IEC 61850 fue evaluado como alternativa a Modbus pero descartado por complejidad de implementación",
            memory_type="observation",
            tags="iec-61850,descartado,evaluacion",
            importance=0.5,
        ),
    ],
)

BRIDGE_REASON = "Los datos de monitorización de inversores alimentan el modelo de mantenimiento predictivo"

ALL_BATCHES = [BATCH_1_CLUSTER, BATCH_2_CONTRADICTION, BATCH_3_CROSS_PROJECT, BATCH_5_COLD]
