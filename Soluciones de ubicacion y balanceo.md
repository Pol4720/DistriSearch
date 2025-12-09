# Plan de Redefinición del Sistema DistriSearch

Basándome en las restricciones (sin hash, sin embeddings pre-entrenados de dimensión fija) y los requerimientos (rebalanceo activo, importancia del nombre del archivo, documentos extensos), propongo el siguiente plan integral:

---

## 1. Nueva Arquitectura de Partición Vectorial

### 1.1 Representación Vectorial Adaptativa (Sin Embeddings Fijos)

**Problema:** Los embeddings pre-entrenados tienen dimensión fija y pierden información en documentos extensos.

**Solución: Vectores TF-IDF Jerárquicos con Reducción Adaptativa**

```
┌─────────────────────────────────────────────────────────────────┐
│                   VECTOR CARACTERÍSTICO                         │
├─────────────────────────────────────────────────────────────────┤
│  NIVEL 1: Vector del Nombre (Alta Prioridad)                    │
│  ├── Tokens del nombre: TF-IDF local                           │
│  ├── N-gramas de caracteres (2,3,4): Captura errores/variantes │
│  └── Categoría inferida (tipo archivo, dominio)                │
├─────────────────────────────────────────────────────────────────┤
│  NIVEL 2: Vector de Contenido (Segmentado)                      │
│  ├── Resumen extractivo (primeras N oraciones)                 │
│  ├── Keywords extraídos con TextRank/RAKE                      │
│  └── Tópicos LDA locales (entrenado en el corpus del cluster)  │
├─────────────────────────────────────────────────────────────────┤
│  NIVEL 3: Metadatos Estructurales                               │
│  ├── Extensión, tamaño, fecha                                  │
│  └── Estructura del documento (secciones, tablas)              │
└─────────────────────────────────────────────────────────────────┘
```

**Técnica: Locality-Sensitive Hashing (LSH) con MinHash para Similaridad**

En lugar de embeddings densos, usaremos:
- **MinHash** para estimar similaridad Jaccard entre conjuntos de tokens
- **LSH (Locality-Sensitive Hashing)** para agrupar documentos similares sin usar hashing tradicional para ubicación

```python
# Pseudocódigo del nuevo sistema de vectorización
class AdaptiveDocumentVector:
    def __init__(self):
        self.name_vector = None      # TF-IDF sparse del nombre
        self.content_signatures = [] # MinHash signatures por segmento
        self.topic_distribution = [] # LDA topics (entrenado localmente)
        self.structural_features = {}
    
    def compute_similarity(self, other) -> float:
        # Similaridad ponderada multi-nivel
        name_sim = cosine_similarity(self.name_vector, other.name_vector)
        content_sim = jaccard_minhash(self.content_signatures, other.content_signatures)
        topic_sim = jensen_shannon_divergence(self.topic_distribution, other.topic_distribution)
        
        # Peso mayor al nombre para archivos sin contenido extraíble
        if self.is_binary:
            return 0.8 * name_sim + 0.2 * topic_sim
        return 0.4 * name_sim + 0.4 * content_sim + 0.2 * topic_sim
```

---

## 2. Partición del Espacio con Árboles de Búsqueda Distribuidos

### 2.1 Ball Tree / VP-Tree Distribuido

**Técnica del Estado del Arte:** Vantage-Point Trees (VP-Trees) para espacios métricos arbitrarios.

```
                    [Centroide Global]
                          │
            ┌─────────────┼─────────────┐
            │             │             │
       [Nodo_1]      [Nodo_2]      [Nodo_3]
       d < r₁        r₁ ≤ d < r₂    d ≥ r₂
         │             │             │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────┐
    │Docs     │   │Docs     │   │Docs     │
    │similar  │   │similar  │   │similar  │
    │a VP₁    │   │a VP₂    │   │a VP₃    │
    └─────────┘   └─────────┘   └─────────┘
```

**Algoritmo de Asignación:**

```python
class VPTreePartitioner:
    """
    Particiona documentos usando VP-Tree.
    Cada nodo del cluster es responsable de una región del espacio.
    """
    
    def __init__(self, nodes: List[str]):
        self.nodes = nodes
        self.vantage_points = {}  # node_id -> vector representativo
        self.radii = {}           # node_id -> radio de cobertura
    
    def assign_document(self, doc_vector: AdaptiveDocumentVector) -> str:
        """Encuentra el nodo más apropiado para un documento."""
        best_node = None
        best_distance = float('inf')
        
        for node_id, vp in self.vantage_points.items():
            distance = doc_vector.compute_distance(vp)
            if distance < best_distance:
                best_distance = distance
                best_node = node_id
        
        return best_node
    
    def recompute_vantage_points(self):
        """Recalcula centroides cuando cambia la topología."""
        # Usa k-medoids (más robusto que k-means para métricas arbitrarias)
        pass
```

---

## 3. Rebalanceo Activo al Añadir Nodos

### 3.1 Algoritmo de Rebalanceo Consistente

**Problema:** Al añadir un nodo, hay que redistribuir archivos manteniendo localidad semántica.

**Solución: Power of Two Choices con Afinidad Semántica**

```
┌──────────────────────────────────────────────────────────────┐
│              PROCESO DE REBALANCEO                           │
├──────────────────────────────────────────────────────────────┤
│ 1. Nuevo nodo N₄ se une al cluster                          │
│                                                              │
│ 2. Master calcula nuevo VP-Tree con N₄                      │
│    - N₄ recibe un "vantage point" inicial (centroide vacío) │
│                                                              │
│ 3. Identificar documentos candidatos a migrar:              │
│    - Docs en nodos sobrecargados (>umbral)                  │
│    - Docs cuyo VP más cercano ahora es N₄                   │
│                                                              │
│ 4. Migración gradual (no disruptiva):                       │
│    - Priorizar docs más cercanos al nuevo VP                │
│    - Transferir en batches durante baja carga               │
│    - Mantener réplica temporal hasta confirmar              │
│                                                              │
│ 5. Actualizar índices y vantage points                      │
└──────────────────────────────────────────────────────────────┘
```

```python
class ActiveRebalancer:
    """Rebalanceo activo al añadir/remover nodos."""
    
    async def on_node_join(self, new_node_id: str):
        """Ejecuta rebalanceo cuando un nodo se une."""
        
        # 1. Calcular carga actual por nodo
        loads = self._get_node_loads()
        avg_load = sum(loads.values()) / len(loads)
        target_load = avg_load  # El nuevo nodo debería alcanzar esto
        
        # 2. Encontrar documentos candidatos a migrar
        candidates = []
        for node_id, load in loads.items():
            if load > avg_load * 1.2:  # Nodo sobrecargado
                docs = self._get_documents_to_migrate(
                    node_id, 
                    target_count=int(load - avg_load),
                    prefer_similar_to_new_vp=True
                )
                candidates.extend(docs)
        
        # 3. Ordenar por afinidad con el nuevo nodo
        new_vp = self._compute_initial_vantage_point(new_node_id, candidates)
        candidates.sort(key=lambda d: d.compute_distance(new_vp))
        
        # 4. Migrar gradualmente
        batch_size = 50
        for batch in chunks(candidates[:int(target_load)], batch_size):
            await self._migrate_batch(batch, new_node_id)
            await asyncio.sleep(1)  # Rate limiting
        
        # 5. Actualizar VP-Tree global
        self._recompute_vantage_points()
    
    def _get_documents_to_migrate(
        self, 
        node_id: str, 
        target_count: int,
        prefer_similar_to_new_vp: bool
    ) -> List[Document]:
        """
        Selecciona documentos para migrar usando criterio de frontera.
        Prioriza documentos en el "borde" de la región del nodo.
        """
        docs = self.partition_index.get_documents_in_node(node_id)
        vp = self.vantage_points[node_id]
        
        # Ordenar por distancia al VP (los más lejanos son candidatos)
        docs.sort(key=lambda d: d.compute_distance(vp), reverse=True)
        
        return docs[:target_count]
```

---

## 4. Sistema de Replicación con Afinidad Semántica

### 4.1 Replicación Basada en Grafos de Similaridad

**Técnica:** Construir un grafo donde los nodos son documentos y las aristas representan similaridad. Las réplicas se colocan en nodos del cluster que contienen documentos "vecinos" en este grafo.

```
     Grafo de Similaridad de Documentos
     
     [Doc_A: ventas_q1.xlsx]
            │ sim=0.85
            ▼
     [Doc_B: ventas_q2.xlsx] ←──sim=0.72──→ [Doc_C: ingresos_2024.csv]
            │ sim=0.68
            ▼
     [Doc_D: reporte_ventas.pdf]

     ═══════════════════════════════════════
     
     Asignación a Nodos del Cluster:
     
     Nodo_1: {Doc_A, Doc_B}  ← Réplica de Doc_C aquí (vecino)
     Nodo_2: {Doc_C, Doc_D}  ← Réplica de Doc_B aquí (vecino)
     Nodo_3: {Réplicas...}
```

```python
class AffinityBasedReplicator:
    """Replicación que mantiene documentos similares cerca."""
    
    def __init__(self, replication_factor: int = 2):
        self.replication_factor = replication_factor
        self.similarity_graph = defaultdict(list)  # doc_id -> [(doc_id, sim)]
    
    def select_replica_nodes(
        self, 
        doc_id: str, 
        source_node: str,
        doc_vector: AdaptiveDocumentVector
    ) -> List[str]:
        """
        Selecciona nodos para réplicas basándose en:
        1. Nodos que tienen documentos similares
        2. Diversidad geográfica/de fallos
        3. Carga actual
        """
        candidates = []
        
        # Encontrar documentos similares y sus nodos
        similar_docs = self._find_similar_documents(doc_vector, top_k=10)
        
        node_affinity_scores = defaultdict(float)
        for sim_doc_id, similarity in similar_docs:
            sim_doc_node = self.partition_index.get_document(sim_doc_id).node_id
            if sim_doc_node != source_node:
                node_affinity_scores[sim_doc_node] += similarity
        
        # Ordenar nodos por afinidad
        sorted_nodes = sorted(
            node_affinity_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Seleccionar top-k asegurando diversidad
        selected = []
        for node_id, affinity in sorted_nodes:
            if len(selected) >= self.replication_factor:
                break
            if self._ensures_fault_tolerance(selected, node_id):
                selected.append(node_id)
        
        # Completar con nodos menos cargados si faltan
        if len(selected) < self.replication_factor:
            remaining = self._get_least_loaded_nodes(
                exclude=selected + [source_node],
                count=self.replication_factor - len(selected)
            )
            selected.extend(remaining)
        
        return selected
    
    def _ensures_fault_tolerance(
        self, 
        current_selection: List[str], 
        candidate: str
    ) -> bool:
        """Verifica que el candidato no esté en el mismo rack/zona."""
        # Implementar lógica de diversidad de fallos
        candidate_zone = self._get_failure_zone(candidate)
        selected_zones = {self._get_failure_zone(n) for n in current_selection}
        return candidate_zone not in selected_zones
```

---

## 5. Recuperación ante Fallos con Re-replicación Inteligente

### 5.1 Detector de Sub-replicación y Recuperación

```python
class FailureRecoveryService:
    """Servicio de recuperación ante fallos de nodos."""
    
    def __init__(self):
        self.replication_tracker = {}  # doc_id -> set(node_ids)
        self.min_replicas = 2
    
    async def on_node_failure(self, failed_node_id: str):
        """Maneja la caída de un nodo."""
        
        # 1. Identificar documentos afectados
        affected_docs = self._get_documents_in_node(failed_node_id)
        
        # 2. Clasificar por urgencia
        critical = []    # Solo quedaba esta réplica
        degraded = []    # Quedan réplicas pero bajo el mínimo
        
        for doc_id in affected_docs:
            remaining_replicas = self.replication_tracker[doc_id] - {failed_node_id}
            if len(remaining_replicas) == 0:
                critical.append((doc_id, None))  # Posible pérdida
            elif len(remaining_replicas) < self.min_replicas:
                degraded.append((doc_id, remaining_replicas))
        
        # 3. Recuperar críticos primero (si hay backup externo)
        for doc_id, _ in critical:
            await self._attempt_recovery_from_backup(doc_id)
        
        # 4. Re-replicar degradados
        for doc_id, remaining_nodes in degraded:
            source_node = next(iter(remaining_nodes))
            await self._re_replicate_document(
                doc_id, 
                source_node,
                target_count=self.min_replicas - len(remaining_nodes)
            )
        
        # 5. Actualizar VP-Tree sin el nodo fallido
        self._recompute_vantage_points()
    
    async def _re_replicate_document(
        self, 
        doc_id: str, 
        source_node: str,
        target_count: int
    ):
        """Re-replica manteniendo afinidad semántica."""
        
        doc = self.partition_index.get_document(doc_id)
        doc_vector = self._get_document_vector(doc_id)
        
        # Seleccionar nuevos nodos para réplicas
        new_targets = self.affinity_replicator.select_replica_nodes(
            doc_id,
            source_node,
            doc_vector
        )[:target_count]
        
        # Ejecutar replicación
        for target_node in new_targets:
            await self._transfer_document(doc_id, source_node, target_node)
            self.replication_tracker[doc_id].add(target_node)
```

---

## 6. Construcción del Vector Característico (Ejemplo Detallado)

### 6.1 Pipeline de Vectorización

```python
class DocumentVectorizer:
    """
    Vectorizador adaptativo que no depende de embeddings pre-entrenados.
    """
    
    def __init__(self):
        # Vocabulario construido desde el corpus (no pre-entrenado)
        self.vocabulary = {}
        self.idf_scores = {}
        
        # LDA entrenado localmente
        self.lda_model = None
        self.num_topics = 20
        
        # N-gramas de caracteres para nombres
        self.char_ngram_range = (2, 4)
    
    def vectorize(self, filename: str, content: Optional[str] = None) -> AdaptiveDocumentVector:
        """
        Construye vector característico completo.
        
        Ejemplo con "ReporteVentas_Q1_2024.xlsx":
        """
        vector = AdaptiveDocumentVector()
        
        # ═══════════════════════════════════════════════════════
        # NIVEL 1: VECTOR DEL NOMBRE (siempre disponible)
        # ═══════════════════════════════════════════════════════
        
        # 1.1 Tokens del nombre
        name_tokens = self._tokenize_filename(filename)
        # Ejemplo: ["reporte", "ventas", "q1", "2024", "reporteventas"]
        
        # 1.2 TF-IDF sparse del nombre
        name_tfidf = self._compute_tfidf(name_tokens, source="name")
        # Ejemplo: {"reporte": 0.34, "ventas": 0.52, "q1": 0.71, "2024": 0.28}
        
        # 1.3 N-gramas de caracteres (robusto a typos)
        char_ngrams = self._extract_char_ngrams(filename)
        # Ejemplo: ["re", "ep", "po", "or", "rt", "rep", "epo", "por", ...]
        
        # 1.4 Categoría inferida
        category = self._infer_category(filename, name_tokens)
        # Ejemplo: {"domain": "finanzas", "type": "reporte", "temporal": "Q1-2024"}
        
        vector.name_vector = {
            "tokens_tfidf": name_tfidf,
            "char_ngrams": self._hash_ngrams_to_signature(char_ngrams),
            "category": category
        }
        
        # ═══════════════════════════════════════════════════════
        # NIVEL 2: VECTOR DE CONTENIDO (si extraíble)
        # ═══════════════════════════════════════════════════════
        
        if content and self._is_text_extractable(filename):
            # 2.1 Segmentar documento largo
            segments = self._segment_document(content, max_tokens=500)
            # Ejemplo: [segment_1, segment_2, ..., segment_n]
            
            # 2.2 MinHash signature por segmento
            for segment in segments:
                segment_tokens = set(self._tokenize_content(segment))
                minhash_sig = self._compute_minhash(segment_tokens, num_hashes=128)
                vector.content_signatures.append(minhash_sig)
            
            # 2.3 Keywords con TextRank
            keywords = self._extract_keywords_textrank(content, top_k=20)
            # Ejemplo: ["ventas", "trimestre", "crecimiento", "margen", "utilidad"]
            
            # 2.4 Distribución de tópicos LDA
            if self.lda_model:
                topic_dist = self._get_topic_distribution(content)
                # Ejemplo: [0.05, 0.02, 0.45, 0.01, ..., 0.12] (20 tópicos)
                vector.topic_distribution = topic_dist
            
            vector.content_keywords = keywords
        
        else:
            # Archivo binario: reforzar peso del nombre
            vector.is_binary = True
            vector.content_signatures = []
            vector.topic_distribution = self._infer_topics_from_name(name_tokens)
        
        # ═══════════════════════════════════════════════════════
        # NIVEL 3: METADATOS ESTRUCTURALES
        # ═══════════════════════════════════════════════════════
        
        vector.structural_features = {
            "extension": Path(filename).suffix.lower(),
            "name_length": len(filename),
            "has_date_pattern": bool(re.search(r'\d{4}|Q[1-4]', filename)),
            "has_version": bool(re.search(r'v\d+|version', filename, re.I)),
        }
        
        return vector
    
    def _compute_minhash(self, token_set: Set[str], num_hashes: int = 128) -> List[int]:
        """
        Calcula MinHash signature para estimación de Jaccard.
        NO usa hash para ubicación, solo para similaridad.
        """
        import mmh3  # MurmurHash3
        
        signature = [float('inf')] * num_hashes
        
        for token in token_set:
            for i in range(num_hashes):
                # Cada "hash function" es mmh3 con seed diferente
                h = mmh3.hash(token, seed=i) & 0xFFFFFFFF
                signature[i] = min(signature[i], h)
        
        return signature
    
    def _extract_keywords_textrank(self, text: str, top_k: int = 20) -> List[str]:
        """
        Extrae keywords usando TextRank (algoritmo estilo PageRank).
        No requiere modelo pre-entrenado.
        """
        sentences = self._split_sentences(text)
        
        # Construir grafo de co-ocurrencia
        word_graph = defaultdict(lambda: defaultdict(float))
        window_size = 5
        
        for sentence in sentences:
            words = self._tokenize_content(sentence)
            for i, word in enumerate(words):
                for j in range(i + 1, min(i + window_size, len(words))):
                    word_graph[word][words[j]] += 1
                    word_graph[words[j]][word] += 1
        
        # PageRank sobre el grafo
        scores = self._pagerank(word_graph, damping=0.85, iterations=30)
        
        # Top-k keywords
        sorted_words = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [word for word, score in sorted_words[:top_k]]
```

### 6.2 Ejemplo Concreto de Vectorización

```
═══════════════════════════════════════════════════════════════════════
DOCUMENTO: "ReporteVentas_Q1_2024.xlsx"
CONTENIDO: "Las ventas del primer trimestre mostraron un crecimiento 
            del 15% respecto al año anterior. El margen operativo..."
═══════════════════════════════════════════════════════════════════════

VECTOR RESULTANTE:

┌─────────────────────────────────────────────────────────────────────┐
│ NIVEL 1 - NOMBRE                                                    │
├─────────────────────────────────────────────────────────────────────┤
│ tokens_tfidf: {                                                     │
│   "reporte": 0.34,                                                 │
│   "ventas": 0.52,                                                  │
│   "q1": 0.71,                                                      │
│   "2024": 0.28,                                                    │
│   "reporteventas": 0.15                                            │
│ }                                                                   │
│                                                                     │
│ char_ngrams_signature: [4521, 8723, 1234, 9876, ...]  (128 valores)│
│                                                                     │
│ category: {                                                         │
│   "domain": "finanzas",                                            │
│   "type": "reporte",                                               │
│   "temporal": "Q1-2024"                                            │
│ }                                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ NIVEL 2 - CONTENIDO                                                 │
├─────────────────────────────────────────────────────────────────────┤
│ content_signatures: [                                               │
│   [2341, 5678, 9012, ...],  # MinHash segmento 1                   │
│   [3456, 7890, 1234, ...]   # MinHash segmento 2                   │
│ ]                                                                   │
│                                                                     │
│ keywords_textrank: [                                                │
│   "ventas", "trimestre", "crecimiento",                            │
│   "margen", "operativo", "año"                                     │
│ ]                                                                   │
│                                                                     │
│ topic_distribution: [                                               │
│   0.02,  # Tópico 0: tecnología                                    │
│   0.01,  # Tópico 1: recursos humanos                              │
│   0.45,  # Tópico 2: FINANZAS ← dominante                          │
│   0.03,  # Tópico 3: legal                                         │
│   ...                                                               │
│   0.12   # Tópico 19: operaciones                                  │
│ ]                                                                   │
├─────────────────────────────────────────────────────────────────────┤
│ NIVEL 3 - ESTRUCTURA                                                │
├─────────────────────────────────────────────────────────────────────┤
│ {                                                                   │
│   "extension": ".xlsx",                                            │
│   "name_length": 24,                                               │
│   "has_date_pattern": true,                                        │
│   "has_version": false                                             │
│ }                                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Elección de Líder Mejorada con Persistencia de Estado

### 7.1 Raft-Lite para Consenso

**Problema:** El algoritmo Bully es simple pero no persiste estado ni maneja split-brain.

**Solución:** Implementar una versión simplificada de Raft para:
- Persistir el índice de particiones
- Consenso sobre quién es líder
- Replicación del log de operaciones

```python
class RaftLiteElection:
    """
    Elección de líder con persistencia de estado.
    Basado en Raft simplificado.
    """
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        
        # Estado persistente (en disco/DB)
        self.current_term = 0
        self.voted_for = None
        self.log = []  # Operaciones del índice
        
        # Estado volátil
        self.state = "follower"  # follower, candidate, leader
        self.leader_id = None
        
        # Timeouts
        self.election_timeout = random.uniform(150, 300)  # ms
        self.heartbeat_interval = 50  # ms
    
    async def on_leader_elected(self):
        """Cuando este nodo se convierte en líder."""
        
        # 1. Cargar estado persistido del índice
        self.partition_index = await self._load_persisted_index()
        
        # 2. Sincronizar con followers
        await self._replicate_index_to_followers()
        
        # 3. Iniciar heartbeats
        asyncio.create_task(self._send_heartbeats())
    
    async def _persist_index_operation(self, operation: Dict):
        """
        Persiste operación en el log antes de aplicarla.
        Garantiza que el estado sobrevive a caídas.
        """
        # Añadir al log local
        self.log.append({
            "term": self.current_term,
            "operation": operation,
            "timestamp": datetime.utcnow()
        })
        
        # Replicar a mayoría antes de confirmar
        acks = await self._replicate_to_followers(operation)
        
        if acks >= len(self.peers) // 2 + 1:
            # Mayoría alcanzada, aplicar operación
            await self._apply_operation(operation)
            return True
        
        return False
```

### 7.2 Manejo de Archivos del Ex-Master

```python
class MasterFailoverHandler:
    """Maneja la transición cuando el master cambia."""
    
    async def on_new_master(self, old_master: str, new_master: str):
        """
        Ejecuta cuando hay un nuevo master.
        """
        
        # 1. El nuevo master carga el índice persistido
        index = await self._load_persisted_partition_index()
        
        # 2. Verificar estado de documentos del ex-master
        old_master_docs = index.get_documents_in_node(old_master)
        
        for doc in old_master_docs:
            # Verificar si hay réplicas disponibles
            replicas = self.replication_tracker.get(doc.file_id, set())
            available_replicas = replicas - {old_master}
            
            if available_replicas:
                # Promover réplica a primaria
                new_primary = next(iter(available_replicas))
                await self._promote_replica(doc.file_id, new_primary)
            else:
                # Marcar como potencialmente perdido
                await self._mark_document_degraded(doc.file_id)
        
        # 3. Si el ex-master era también un slave con archivos
        if old_master in self.slave_nodes:
            # Sus archivos quedan inaccesibles hasta que reviva
            # O hasta que se recuperen de réplicas
            await self._handle_slave_failure(old_master)
        
        # 4. Actualizar VP-Tree sin el ex-master
        await self._recompute_partitions()
```

---

## 8. Resumen del Plan de Implementación

### Fase 1: Vectorización Adaptativa
- [ ] Implementar `AdaptiveDocumentVector` con TF-IDF + MinHash
- [ ] Agregar extracción de keywords con TextRank
- [ ] Entrenar LDA local sobre el corpus existente
- [ ] Crear n-gramas de caracteres para nombres

### Fase 2: Partición con VP-Tree
- [ ] Implementar `VPTreePartitioner`
- [ ] Definir métrica de distancia multi-nivel
- [ ] Integrar con `PartitionIndex` existente

### Fase 3: Rebalanceo Activo
- [ ] Implementar `ActiveRebalancer.on_node_join()`
- [ ] Crear endpoint para migración de documentos
- [ ] Añadir lógica de selección de candidatos a migrar

### Fase 4: Replicación con Afinidad
- [ ] Implementar grafo de similaridad entre documentos
- [ ] Modificar `ReplicationCoordinator` para usar afinidad
- [ ] Añadir tracking de réplicas activas

### Fase 5: Recuperación Mejorada
- [ ] Implementar `FailureRecoveryService`
- [ ] Añadir re-replicación automática
- [ ] Crear sistema de alertas para documentos degradados

### Fase 6: Elección con Persistencia
- [ ] Implementar `RaftLiteElection`
- [ ] Persistir `PartitionIndex` en MongoDB
- [ ] Añadir log de operaciones replicado
