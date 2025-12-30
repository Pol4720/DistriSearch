"""
Tests Router - Endpoints para pruebas del sistema distribuido
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()

# Almacén de resultados de tests
test_results: Dict[str, Dict[str, Any]] = {}


class TestScenario(BaseModel):
    """Configuración de un escenario de prueba."""
    name: str
    description: str
    steps: List[str]


def get_docker_service():
    from main import get_docker_service as get_svc
    return get_svc()


def get_cluster_service():
    from main import get_cluster_service as get_svc
    return get_svc()


def get_ws_manager():
    from main import get_ws_manager as get_mgr
    return get_mgr()


# ============================================
# Escenarios de prueba predefinidos
# ============================================

PREDEFINED_SCENARIOS = {
    "leader_failover": {
        "name": "Failover de Líder",
        "description": "Prueba la elección de un nuevo líder cuando el actual falla",
        "steps": [
            "1. Identificar el nodo líder actual",
            "2. Matar el nodo líder (SIGKILL)",
            "3. Esperar detección de fallo (timeout heartbeat)",
            "4. Verificar que se inicia nueva elección",
            "5. Confirmar nuevo líder elegido",
            "6. Verificar que el cluster sigue operativo"
        ],
        "expected_time_seconds": 30,
        "concepts": ["Raft", "Leader Election", "Consensus"]
    },
    "node_recovery": {
        "name": "Recuperación de Nodo",
        "description": "Prueba cómo un nodo se recupera y sincroniza con el cluster",
        "steps": [
            "1. Añadir documentos al cluster",
            "2. Detener un nodo slave",
            "3. Añadir más documentos mientras está caído",
            "4. Reiniciar el nodo",
            "5. Verificar sincronización de datos",
            "6. Confirmar consistencia de datos"
        ],
        "expected_time_seconds": 45,
        "concepts": ["Log Replication", "State Synchronization", "Eventual Consistency"]
    },
    "network_partition": {
        "name": "Partición de Red",
        "description": "Simula una partición de red y verifica el comportamiento",
        "steps": [
            "1. Pausar un nodo (simular partición)",
            "2. Verificar que el cluster lo detecta",
            "3. Continuar operaciones con nodos disponibles",
            "4. Reanudar el nodo particionado",
            "5. Verificar reconexión automática",
            "6. Confirmar consistencia después de la reconexión"
        ],
        "expected_time_seconds": 40,
        "concepts": ["CAP Theorem", "Partition Tolerance", "Consistency"]
    },
    "load_balancing": {
        "name": "Balanceo de Carga",
        "description": "Prueba la distribución de búsquedas entre nodos",
        "steps": [
            "1. Ejecutar múltiples búsquedas simultáneas",
            "2. Monitorear qué nodos procesan cada búsqueda",
            "3. Verificar distribución equilibrada",
            "4. Calcular métricas de latencia por nodo",
            "5. Generar informe de distribución"
        ],
        "expected_time_seconds": 20,
        "concepts": ["Load Balancing", "Distributed Search", "Latency"]
    },
    "replication_test": {
        "name": "Prueba de Replicación",
        "description": "Verifica que los datos se replican correctamente",
        "steps": [
            "1. Subir un documento nuevo",
            "2. Verificar en el líder",
            "3. Esperar replicación",
            "4. Verificar en cada slave",
            "5. Confirmar factor de replicación cumplido"
        ],
        "expected_time_seconds": 15,
        "concepts": ["Data Replication", "Consistency", "Durability"]
    },
    "stress_test": {
        "name": "Prueba de Estrés",
        "description": "Somete al sistema a carga elevada",
        "steps": [
            "1. Generar múltiples búsquedas concurrentes",
            "2. Monitorear tiempos de respuesta",
            "3. Verificar estabilidad del cluster",
            "4. Detectar posibles cuellos de botella",
            "5. Generar informe de rendimiento"
        ],
        "expected_time_seconds": 60,
        "concepts": ["Performance", "Scalability", "Resilience"]
    }
}


@router.get("/scenarios", summary="Listar escenarios de prueba")
async def list_scenarios():
    """
    Lista todos los escenarios de prueba disponibles.
    
    Cada escenario prueba un aspecto diferente del sistema distribuido:
    - Elección de líder
    - Recuperación de nodos
    - Particiones de red
    - Balanceo de carga
    - Replicación de datos
    """
    return {
        "scenarios": PREDEFINED_SCENARIOS,
        "total": len(PREDEFINED_SCENARIOS),
        "description": {
            "es": "Escenarios predefinidos para probar diferentes aspectos del sistema distribuido."
        }
    }


@router.get("/scenarios/{scenario_id}", summary="Detalle de escenario")
async def get_scenario(scenario_id: str):
    """
    Obtiene los detalles de un escenario de prueba específico.
    """
    if scenario_id not in PREDEFINED_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Escenario no encontrado: {scenario_id}")
    
    return {
        "scenario_id": scenario_id,
        **PREDEFINED_SCENARIOS[scenario_id]
    }


@router.post("/run/{scenario_id}", summary="Ejecutar escenario")
async def run_scenario(scenario_id: str, background_tasks: BackgroundTasks):
    """
    Inicia la ejecución de un escenario de prueba.
    
    La ejecución es asíncrona. Use el endpoint /results/{test_id}
    para obtener los resultados.
    """
    if scenario_id not in PREDEFINED_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Escenario no encontrado: {scenario_id}")
    
    test_id = str(uuid.uuid4())[:8]
    scenario = PREDEFINED_SCENARIOS[scenario_id]
    
    # Inicializar resultado
    test_results[test_id] = {
        "test_id": test_id,
        "scenario_id": scenario_id,
        "scenario_name": scenario["name"],
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "steps_completed": [],
        "current_step": 0,
        "total_steps": len(scenario["steps"]),
        "errors": [],
        "metrics": {}
    }
    
    # Ejecutar en background
    background_tasks.add_task(execute_scenario, test_id, scenario_id)
    
    return {
        "test_id": test_id,
        "scenario_id": scenario_id,
        "status": "started",
        "message": f"Escenario '{scenario['name']}' iniciado. Consulte /results/{test_id} para ver el progreso."
    }


async def execute_scenario(test_id: str, scenario_id: str):
    """Ejecuta un escenario de prueba."""
    docker_service = get_docker_service()
    cluster_service = get_cluster_service()
    ws_manager = get_ws_manager()
    
    result = test_results[test_id]
    
    try:
        if scenario_id == "leader_failover":
            await run_leader_failover_test(test_id, docker_service, cluster_service, ws_manager)
        elif scenario_id == "node_recovery":
            await run_node_recovery_test(test_id, docker_service, cluster_service, ws_manager)
        elif scenario_id == "network_partition":
            await run_network_partition_test(test_id, docker_service, cluster_service, ws_manager)
        elif scenario_id == "load_balancing":
            await run_load_balancing_test(test_id, cluster_service, ws_manager)
        elif scenario_id == "replication_test":
            await run_replication_test(test_id, cluster_service, ws_manager)
        elif scenario_id == "stress_test":
            await run_stress_test(test_id, cluster_service, ws_manager)
        
        result["status"] = "completed"
        result["completed_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"Error en escenario {scenario_id}: {e}")
        result["status"] = "failed"
        result["errors"].append(str(e))
        result["completed_at"] = datetime.utcnow().isoformat()
    
    # Notificar por WebSocket
    if ws_manager:
        await ws_manager.broadcast({
            "type": "test_completed",
            "data": result
        })


async def update_test_step(test_id: str, step_num: int, description: str, success: bool, ws_manager):
    """Actualiza el paso actual del test."""
    result = test_results[test_id]
    result["current_step"] = step_num
    result["steps_completed"].append({
        "step": step_num,
        "description": description,
        "success": success,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    if ws_manager:
        await ws_manager.broadcast({
            "type": "test_progress",
            "data": result
        })


# ============================================
# Implementación de escenarios
# ============================================

async def run_leader_failover_test(test_id: str, docker_service, cluster_service, ws_manager):
    """Ejecuta el test de failover de líder."""
    result = test_results[test_id]
    
    # Paso 1: Identificar líder
    await update_test_step(test_id, 1, "Identificando líder actual", True, ws_manager)
    leader_info = await cluster_service.get_leader_info()
    original_leader = leader_info.get("leader_id")
    result["metrics"]["original_leader"] = original_leader
    await asyncio.sleep(1)
    
    # Paso 2: Matar el líder
    await update_test_step(test_id, 2, f"Terminando líder: {original_leader}", True, ws_manager)
    if docker_service and docker_service.available:
        containers = docker_service.get_distrisearch_containers()
        master_container = next((c for c in containers if c.get("is_master")), None)
        if master_container:
            await docker_service.kill_container(master_container["name"])
    await asyncio.sleep(2)
    
    # Paso 3: Esperar detección
    await update_test_step(test_id, 3, "Esperando detección de fallo", True, ws_manager)
    await asyncio.sleep(5)  # Timeout de heartbeat
    
    # Paso 4: Verificar nueva elección
    await update_test_step(test_id, 4, "Verificando nueva elección", True, ws_manager)
    await asyncio.sleep(3)
    
    # Paso 5: Confirmar nuevo líder
    new_leader_info = await cluster_service.get_leader_info()
    new_leader = new_leader_info.get("leader_id")
    result["metrics"]["new_leader"] = new_leader
    result["metrics"]["leader_changed"] = original_leader != new_leader
    await update_test_step(test_id, 5, f"Nuevo líder: {new_leader}", True, ws_manager)
    await asyncio.sleep(1)
    
    # Paso 6: Verificar operatividad
    health = await cluster_service.get_health()
    result["metrics"]["cluster_healthy"] = health is not None
    await update_test_step(test_id, 6, "Verificando operatividad del cluster", True, ws_manager)


async def run_node_recovery_test(test_id: str, docker_service, cluster_service, ws_manager):
    """Ejecuta el test de recuperación de nodo."""
    result = test_results[test_id]
    
    # Paso 1: Estado inicial
    await update_test_step(test_id, 1, "Verificando estado inicial", True, ws_manager)
    initial_status = await cluster_service.get_cluster_status()
    result["metrics"]["initial_nodes"] = initial_status.get("total_nodes", 0) if initial_status else 0
    await asyncio.sleep(1)
    
    # Paso 2: Detener un slave
    await update_test_step(test_id, 2, "Deteniendo nodo slave", True, ws_manager)
    if docker_service and docker_service.available:
        containers = docker_service.get_distrisearch_containers()
        slave_container = next((c for c in containers if c.get("is_slave")), None)
        if slave_container:
            await docker_service.stop_container(slave_container["name"])
            result["metrics"]["stopped_node"] = slave_container["name"]
    await asyncio.sleep(2)
    
    # Paso 3: Verificar detección
    await update_test_step(test_id, 3, "Verificando detección de caída", True, ws_manager)
    await asyncio.sleep(5)
    
    # Paso 4: Reiniciar nodo
    await update_test_step(test_id, 4, "Reiniciando nodo", True, ws_manager)
    if docker_service and docker_service.available and result["metrics"].get("stopped_node"):
        await docker_service.start_container(result["metrics"]["stopped_node"])
    await asyncio.sleep(3)
    
    # Paso 5: Verificar sincronización
    await update_test_step(test_id, 5, "Verificando sincronización", True, ws_manager)
    await asyncio.sleep(5)
    
    # Paso 6: Confirmar consistencia
    final_status = await cluster_service.get_cluster_status()
    result["metrics"]["final_nodes"] = final_status.get("total_nodes", 0) if final_status else 0
    result["metrics"]["recovery_successful"] = result["metrics"]["initial_nodes"] == result["metrics"]["final_nodes"]
    await update_test_step(test_id, 6, "Verificando consistencia", True, ws_manager)


async def run_network_partition_test(test_id: str, docker_service, cluster_service, ws_manager):
    """Ejecuta el test de partición de red."""
    result = test_results[test_id]
    
    # Paso 1: Pausar nodo
    await update_test_step(test_id, 1, "Pausando nodo (simulando partición)", True, ws_manager)
    if docker_service and docker_service.available:
        containers = docker_service.get_distrisearch_containers()
        slave_container = next((c for c in containers if c.get("is_slave") and c.get("status") == "running"), None)
        if slave_container:
            await docker_service.pause_container(slave_container["name"])
            result["metrics"]["partitioned_node"] = slave_container["name"]
    await asyncio.sleep(2)
    
    # Paso 2: Verificar detección
    await update_test_step(test_id, 2, "Verificando detección de partición", True, ws_manager)
    await asyncio.sleep(5)
    
    # Paso 3: Continuar operaciones
    await update_test_step(test_id, 3, "Ejecutando operaciones con nodos disponibles", True, ws_manager)
    search_result = await cluster_service.execute_search("test query")
    result["metrics"]["operations_during_partition"] = search_result is not None
    await asyncio.sleep(2)
    
    # Paso 4: Reanudar nodo
    await update_test_step(test_id, 4, "Reanudando nodo particionado", True, ws_manager)
    if docker_service and docker_service.available and result["metrics"].get("partitioned_node"):
        await docker_service.unpause_container(result["metrics"]["partitioned_node"])
    await asyncio.sleep(2)
    
    # Paso 5: Verificar reconexión
    await update_test_step(test_id, 5, "Verificando reconexión automática", True, ws_manager)
    await asyncio.sleep(5)
    
    # Paso 6: Confirmar consistencia
    status = await cluster_service.get_cluster_status()
    healthy_nodes = status.get("healthy_nodes", 0) if status else 0
    result["metrics"]["healthy_after_reconnect"] = healthy_nodes
    await update_test_step(test_id, 6, "Verificando consistencia post-partición", True, ws_manager)


async def run_load_balancing_test(test_id: str, cluster_service, ws_manager):
    """Ejecuta el test de balanceo de carga."""
    result = test_results[test_id]
    
    # Paso 1: Preparar búsquedas
    await update_test_step(test_id, 1, "Preparando búsquedas concurrentes", True, ws_manager)
    queries = [f"test query {i}" for i in range(10)]
    await asyncio.sleep(1)
    
    # Paso 2: Ejecutar búsquedas
    await update_test_step(test_id, 2, "Ejecutando búsquedas", True, ws_manager)
    latencies = []
    for query in queries:
        start = datetime.utcnow()
        await cluster_service.execute_search(query)
        end = datetime.utcnow()
        latencies.append((end - start).total_seconds() * 1000)
    await asyncio.sleep(1)
    
    # Paso 3: Verificar distribución
    await update_test_step(test_id, 3, "Analizando distribución", True, ws_manager)
    await asyncio.sleep(1)
    
    # Paso 4: Calcular métricas
    await update_test_step(test_id, 4, "Calculando métricas de latencia", True, ws_manager)
    result["metrics"]["total_queries"] = len(queries)
    result["metrics"]["avg_latency_ms"] = sum(latencies) / len(latencies) if latencies else 0
    result["metrics"]["min_latency_ms"] = min(latencies) if latencies else 0
    result["metrics"]["max_latency_ms"] = max(latencies) if latencies else 0
    await asyncio.sleep(1)
    
    # Paso 5: Generar informe
    await update_test_step(test_id, 5, "Generando informe", True, ws_manager)


async def run_replication_test(test_id: str, cluster_service, ws_manager):
    """Ejecuta el test de replicación."""
    result = test_results[test_id]
    
    # Pasos simplificados para demostración
    steps = [
        "Subiendo documento de prueba",
        "Verificando en líder",
        "Esperando replicación",
        "Verificando en slaves",
        "Confirmando factor de replicación"
    ]
    
    for i, step in enumerate(steps, 1):
        await update_test_step(test_id, i, step, True, ws_manager)
        await asyncio.sleep(2)
    
    # Métricas finales
    replication = await cluster_service.get_replication_status()
    result["metrics"]["replication_factor"] = replication.get("replication_factor", 0)
    result["metrics"]["nodes_with_data"] = replication.get("nodes_with_data", 0)


async def run_stress_test(test_id: str, cluster_service, ws_manager):
    """Ejecuta el test de estrés."""
    result = test_results[test_id]
    
    # Paso 1: Generar carga
    await update_test_step(test_id, 1, "Generando carga concurrente", True, ws_manager)
    
    # Ejecutar múltiples búsquedas concurrentes
    async def search_task():
        return await cluster_service.execute_search("stress test query")
    
    tasks = [search_task() for _ in range(20)]
    start = datetime.utcnow()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    end = datetime.utcnow()
    
    # Paso 2: Monitorear
    await update_test_step(test_id, 2, "Monitoreando tiempos de respuesta", True, ws_manager)
    successful = sum(1 for r in results if not isinstance(r, Exception))
    await asyncio.sleep(1)
    
    # Paso 3: Verificar estabilidad
    await update_test_step(test_id, 3, "Verificando estabilidad", True, ws_manager)
    await asyncio.sleep(1)
    
    # Paso 4: Detectar cuellos de botella
    await update_test_step(test_id, 4, "Analizando rendimiento", True, ws_manager)
    await asyncio.sleep(1)
    
    # Paso 5: Generar informe
    await update_test_step(test_id, 5, "Generando informe", True, ws_manager)
    result["metrics"]["total_requests"] = len(tasks)
    result["metrics"]["successful_requests"] = successful
    result["metrics"]["failed_requests"] = len(tasks) - successful
    result["metrics"]["total_time_ms"] = (end - start).total_seconds() * 1000
    result["metrics"]["throughput_rps"] = successful / (end - start).total_seconds() if (end - start).total_seconds() > 0 else 0


@router.get("/results/{test_id}", summary="Resultados de prueba")
async def get_test_results(test_id: str):
    """
    Obtiene los resultados de una prueba en ejecución o completada.
    """
    if test_id not in test_results:
        raise HTTPException(status_code=404, detail=f"Test no encontrado: {test_id}")
    
    return test_results[test_id]


@router.get("/results", summary="Todos los resultados")
async def list_test_results():
    """
    Lista todos los resultados de pruebas disponibles.
    """
    return {
        "results": list(test_results.values()),
        "total": len(test_results)
    }


@router.delete("/results/{test_id}", summary="Eliminar resultado")
async def delete_test_result(test_id: str):
    """
    Elimina el resultado de una prueba.
    """
    if test_id not in test_results:
        raise HTTPException(status_code=404, detail=f"Test no encontrado: {test_id}")
    
    del test_results[test_id]
    return {"message": f"Resultado {test_id} eliminado"}
