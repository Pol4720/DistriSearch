# MinHash y Locality-Sensitive Hashing (LSH)

## Estimación Eficiente de Similaridad Jaccard

---

## 1. El Problema de la Similaridad

Comparar dos documentos usando sus conjuntos de tokens es costoso:

- Documento A: 10,000 tokens únicos
- Documento B: 12,000 tokens únicos
- Calcular Jaccard directamente: O(n + m) por par

Con millones de documentos, esto es **prohibitivo**.

---

## 2. Similaridad de Jaccard

La **similaridad de Jaccard** mide el solapamiento entre dos conjuntos:

$$
J(A, B) = \frac{|A \cap B|}{|A \cup B|}
$$

**Ejemplo:**
```
A = {ventas, trimestre, crecimiento, margen}
B = {ventas, año, crecimiento, ingresos}

Intersección = {ventas, crecimiento} → |A ∩ B| = 2
Unión = {ventas, trimestre, crecimiento, margen, año, ingresos} → |A ∪ B| = 6

J(A, B) = 2/6 = 0.33
```

---

## 3. MinHash: La Solución

**MinHash** permite **estimar** la similaridad de Jaccard usando firmas compactas.

### 3.1 Intuición

Si tomamos una función hash $h$ y aplicamos a todos los elementos de un conjunto, el **mínimo** hash tiene la misma probabilidad de provenir de cualquier elemento.

**Propiedad clave:**

$$
P(min(h(A)) = min(h(B))) = J(A, B)
$$

La probabilidad de que el mínimo hash coincida es exactamente la similaridad de Jaccard.

### 3.2 Firma MinHash

Usamos **múltiples funciones hash** $(h_1, h_2, ..., h_k)$ para crear una "firma":

$$
\text{Signature}(A) = [min(h_1(A)), min(h_2(A)), ..., min(h_k(A))]
$$

```
┌─────────────────────────────────────────────────────────────────┐
│                    FIRMA MINHASH                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Documento: {ventas, trimestre, crecimiento}                   │
│                                                                 │
│  h₁(ventas)=42, h₁(trimestre)=78, h₁(crecimiento)=15          │
│  → min₁ = 15                                                    │
│                                                                 │
│  h₂(ventas)=91, h₂(trimestre)=23, h₂(crecimiento)=67          │
│  → min₂ = 23                                                    │
│                                                                 │
│  ...                                                            │
│                                                                 │
│  Firma = [15, 23, 56, 8, 102, ...]  (128 valores)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementación en DistriSearch

```python
# backend/app/core/vectorization/minhash_signature.py

from datasketch import MinHash, MinHashLSH

class MinHashSignature:
    """
    Generador de firmas MinHash para estimación de similaridad.
    """
    
    def __init__(self, num_perm: int = 128, seed: int = 42):
        """
        Args:
            num_perm: Número de permutaciones (tamaño de firma)
            seed: Semilla para reproducibilidad
        """
        self.num_perm = num_perm
        self.seed = seed
    
    def compute_signature(self, tokens: Set[str]) -> List[int]:
        """
        Calcula firma MinHash para un conjunto de tokens.
        """
        if not tokens:
            return [0] * self.num_perm
        
        minhash = MinHash(num_perm=self.num_perm, seed=self.seed)
        
        for token in tokens:
            minhash.update(token.encode('utf-8'))
        
        return list(minhash.hashvalues)
    
    def estimate_similarity(self, sig1: List[int], sig2: List[int]) -> float:
        """
        Estima similaridad Jaccard desde dos firmas.
        
        Similaridad = (coincidencias) / (total de hashes)
        """
        if len(sig1) != len(sig2):
            raise ValueError("Firmas deben tener mismo tamaño")
        
        matches = sum(1 for h1, h2 in zip(sig1, sig2) if h1 == h2)
        
        return matches / len(sig1)
```

### 4.1 Error de Estimación

El error estándar de la estimación es:

$$
\sigma = \sqrt{\frac{J(1-J)}{k}}
$$

Con $k = 128$ permutaciones y $J = 0.5$:

$$
\sigma = \sqrt{\frac{0.5 \times 0.5}{128}} \approx 0.044
$$

**Error típico: ±4.4%** - suficientemente preciso para búsqueda.

---

## 5. LSH: Locality-Sensitive Hashing

**LSH** acelera la búsqueda de documentos similares **sin comparar todos los pares**.

### 5.1 Concepto

Dividimos la firma MinHash en **bandas**. Dos documentos son candidatos si coinciden en **al menos una banda completa**.

```
┌─────────────────────────────────────────────────────────────────┐
│                    LSH CON BANDAS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Firma de 128 valores → 16 bandas de 8 valores cada una        │
│                                                                 │
│  Doc A: [15,23,56,8 | 102,45,67,89 | 12,34,56,78 | ...]        │
│  Doc B: [15,23,56,8 | 102,45,67,89 | 99,11,22,33 | ...]        │
│           ═════════                                             │
│           Banda 1: COINCIDE ← Son candidatos                   │
│                                                                 │
│  Doc C: [99,88,77,66 | 55,44,33,22 | 11,00,99,88 | ...]        │
│  Doc A vs C: Ninguna banda coincide ← NO son candidatos        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Probabilidad de Ser Candidatos

Con $b$ bandas y $r$ filas por banda:

$$
P(\text{candidato}) = 1 - (1 - J^r)^b
$$

**Ejemplo con 16 bandas, 8 filas:**

| Jaccard Real | P(candidato) |
|--------------|--------------|
| 0.2 | 0.02% |
| 0.4 | 2.8% |
| 0.5 | 18% |
| 0.6 | 57% |
| 0.8 | 99.7% |

---

## 6. Implementación LSH en DistriSearch

```python
# backend/app/core/vectorization/minhash_signature.py

class MinHashLSHIndex:
    """
    Índice LSH para búsqueda aproximada de vecinos cercanos.
    """
    
    def __init__(
        self,
        threshold: float = 0.5,
        num_perm: int = 128,
        seed: int = 42
    ):
        """
        Args:
            threshold: Umbral de similaridad Jaccard para matching
            num_perm: Número de permutaciones
        """
        self.threshold = threshold
        self.num_perm = num_perm
        
        self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._minhashes: dict = {}
        self._signature_gen = MinHashSignature(num_perm=num_perm, seed=seed)
    
    def add(self, doc_id: str, tokens: Set[str]):
        """Agrega documento al índice."""
        minhash = self._signature_gen.create_minhash(tokens)
        
        self._lsh.insert(doc_id, minhash)
        self._minhashes[doc_id] = minhash
    
    def query(self, tokens: Set[str]) -> List[str]:
        """
        Busca documentos similares.
        
        Retorna IDs de documentos candidatos.
        """
        minhash = self._signature_gen.create_minhash(tokens)
        return list(self._lsh.query(minhash))
    
    def query_with_scores(
        self, 
        tokens: Set[str], 
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Busca documentos similares con scores.
        """
        query_minhash = self._signature_gen.create_minhash(tokens)
        candidates = self._lsh.query(query_minhash)
        
        # Calcular similaridad exacta para candidatos
        results = []
        for doc_id in candidates:
            doc_minhash = self._minhashes[doc_id]
            similarity = query_minhash.jaccard(doc_minhash)
            results.append((doc_id, similarity))
        
        # Ordenar por similaridad descendente
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
```

---

## 7. Aplicación: Contenido Segmentado

Para documentos largos, aplicamos MinHash por **segmentos**:

```python
# backend/app/core/vectorization/minhash_signature.py

class ContentMinHasher:
    """MinHash para contenido segmentado."""
    
    def __init__(self, num_perm: int = 128, segment_size: int = 1000):
        self.num_perm = num_perm
        self.segment_size = segment_size
        self._signature_gen = MinHashSignature(num_perm=num_perm)
    
    def compute_segmented_signatures(self, content: str) -> List[List[int]]:
        """
        Computa firmas MinHash por segmento.
        
        Documento largo → [firma_seg1, firma_seg2, ...]
        """
        tokens = self._tokenize(content)
        segments = self._segment_tokens(tokens)
        
        signatures = []
        for segment in segments:
            sig = self._signature_gen.compute_signature(set(segment))
            signatures.append(sig)
        
        return signatures
    
    def compute_combined_similarity(
        self, 
        sigs1: List[List[int]], 
        sigs2: List[List[int]]
    ) -> float:
        """
        Similaridad combinada entre documentos segmentados.
        
        Usa el máximo de todas las comparaciones segmento-a-segmento.
        """
        if not sigs1 or not sigs2:
            return 0.0
        
        max_sim = 0.0
        for s1 in sigs1:
            for s2 in sigs2:
                sim = self._signature_gen.estimate_similarity(s1, s2)
                max_sim = max(max_sim, sim)
        
        return max_sim
```

---

## 8. Ventajas para Búsqueda Distribuida

| Aspecto | Beneficio en DistriSearch |
|---------|---------------------------|
| **Compresión** | Documento → 128 enteros (512 bytes) |
| **Comparación rápida** | O(k) en lugar de O(n+m) |
| **Escalable** | LSH reduce candidatos drásticamente |
| **Distribuible** | Firmas viajan fácilmente entre nodos |
| **No usa hash para ubicación** | Cumple restricción del proyecto |

---

## 9. Flujo en Búsqueda

```
┌─────────────────────────────────────────────────────────────────┐
│                 BÚSQUEDA CON MINHASH LSH                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Query: "reporte ventas trimestral"                         │
│                                                                 │
│  2. Tokenizar → {reporte, ventas, trimestral}                  │
│                                                                 │
│  3. Calcular MinHash → [42, 78, 15, 91, 23, ...]               │
│                                                                 │
│  4. LSH Query → Candidatos: [doc_123, doc_456, doc_789]        │
│                 (de 100,000 docs, solo 3 candidatos)           │
│                                                                 │
│  5. Calcular similaridad exacta para candidatos                │
│                                                                 │
│  6. Ranking final:                                              │
│     - doc_123: 0.85                                             │
│     - doc_456: 0.72                                             │
│     - doc_789: 0.61                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Comparación de Complejidad

| Operación | Sin LSH | Con LSH |
|-----------|---------|---------|
| Indexar N docs | O(N) | O(N) |
| Buscar en N docs | O(N) | O(1) promedio |
| Comparar par | O(tokens) | O(k) = O(128) |
| Espacio por doc | O(tokens) | O(k) = O(128) |

---

> **Anterior**: [01_TF_IDF_Jerarquico.md](01_TF_IDF_Jerarquico.md)
> 
> **Siguiente**: [03_Vector_Caracteristico_Adaptativo.md](03_Vector_Caracteristico_Adaptativo.md)