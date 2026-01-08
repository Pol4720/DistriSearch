# Vector Característico Adaptativo

## Representación Multi-Nivel de Documentos

---

## 1. Concepto General

El **AdaptiveDocumentVector** es la estructura central que representa un documento en DistriSearch. Se adapta según el tipo y contenido del documento.

```
┌─────────────────────────────────────────────────────────────────┐
│                 ADAPTIVE DOCUMENT VECTOR                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ NIVEL 1: NameVector                                      │   │
│  │ ├── tokens_tfidf: Dict[str, float]                      │   │
│  │ ├── char_ngrams_signature: List[int]                    │   │
│  │ └── category: Dict[str, str]                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ NIVEL 2: ContentVector                                   │   │
│  │ ├── minhash_signatures: List[List[int]]                 │   │
│  │ ├── keywords_textrank: List[str]                        │   │
│  │ └── topic_distribution: List[float]                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ NIVEL 3: StructuralFeatures                              │   │
│  │ ├── extension: str                                       │   │
│  │ ├── name_length: int                                     │   │
│  │ ├── has_date_pattern: bool                               │   │
│  │ └── has_version: bool                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  PESOS ADAPTATIVOS                                              │
│  ├── name_weight: 0.4 (ajustable)                              │
│  ├── content_weight: 0.4 (ajustable)                           │
│  └── topic_weight: 0.2 (ajustable)                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Definición en Código

```python
# shared/models/document.py

from pydantic import BaseModel
from typing import Dict, List, Optional

class NameVector(BaseModel):
    """Vector del nombre del archivo."""
    tokens_tfidf: Dict[str, float] = {}
    char_ngrams_signature: List[int] = []
    category: Dict[str, str] = {}

class ContentVector(BaseModel):
    """Vector del contenido."""
    minhash_signatures: List[List[int]] = []
    keywords_textrank: List[str] = []
    topic_distribution: List[float] = []

class StructuralFeatures(BaseModel):
    """Características estructurales."""
    extension: str = ""
    name_length: int = 0
    file_size: int = 0
    has_date_pattern: bool = False
    has_version: bool = False
    section_count: int = 0
    has_tables: bool = False

class DocumentVector(BaseModel):
    """Vector completo del documento."""
    name_vector: NameVector
    content_vector: ContentVector
    structural_features: StructuralFeatures
    
    # Pesos adaptativos
    name_weight: float = 0.4
    content_weight: float = 0.4
    topic_weight: float = 0.2
```

---

## 3. Cálculo de Similaridad Multi-Nivel

La similaridad total se calcula combinando los tres niveles:

$$
S_{total} = w_{name} \cdot S_{name} + w_{content} \cdot S_{content} + w_{topic} \cdot S_{topic}
$$

### 3.1 Implementación

```python
# backend/app/core/vectorization/document_vectorizer.py

def compute_similarity(
    self,
    vec1: DocumentVector,
    vec2: DocumentVector
) -> float:
    """
    Calcula similaridad ponderada entre dos vectores.
    """
    # Similaridad del nombre
    name_sim = self._compute_name_similarity(
        vec1.name_vector, vec2.name_vector
    )
    
    # Similaridad del contenido
    content_sim = self._compute_content_similarity(
        vec1.content_vector, vec2.content_vector
    )
    
    # Similaridad de tópicos
    topic_sim = self._compute_topic_similarity(
        vec1.content_vector, vec2.content_vector
    )
    
    # Combinación ponderada
    total = (
        self.name_weight * name_sim +
        self.content_weight * content_sim +
        self.topic_weight * topic_sim
    )
    
    return total
```

---

## 4. Similaridad del Nombre (name_sim)

Combina TF-IDF coseno + n-gramas + bonus de categoría:

```python
def _compute_name_similarity(
    self,
    nv1: NameVector,
    nv2: NameVector
) -> float:
    """
    Similaridad entre vectores de nombre.
    """
    # 1. Coseno TF-IDF
    tfidf_sim = self.content_tfidf.compute_similarity_from_dicts(
        nv1.tokens_tfidf,
        nv2.tokens_tfidf
    )
    
    # 2. Similaridad de n-gramas de caracteres
    ngram_sim = self.char_ngram.estimate_similarity_from_signatures(
        nv1.char_ngrams_signature,
        nv2.char_ngrams_signature
    )
    
    # 3. Bonus por categoría coincidente
    category_bonus = 0.0
    if nv1.category and nv2.category:
        if nv1.category.get('domain') == nv2.category.get('domain'):
            category_bonus += 0.1
        if nv1.category.get('type') == nv2.category.get('type'):
            category_bonus += 0.05
    
    # Combinar
    base_sim = 0.6 * tfidf_sim + 0.4 * ngram_sim
    
    return min(1.0, base_sim + category_bonus)
```

**Fórmula:**

$$
S_{name} = \min(1.0, \underbrace{0.6 \cdot \cos(TF_1, TF_2)}_{\text{TF-IDF}} + \underbrace{0.4 \cdot J(ng_1, ng_2)}_{\text{n-gramas}} + \underbrace{bonus}_{\text{categoría}})
$$

---

## 5. Similaridad del Contenido (content_sim)

Usa MinHash Jaccard sobre segmentos:

```python
def _compute_content_similarity(
    self,
    cv1: ContentVector,
    cv2: ContentVector
) -> float:
    """
    Similaridad entre vectores de contenido.
    """
    if not cv1.minhash_signatures or not cv2.minhash_signatures:
        return 0.0
    
    # Usar el máximo entre todos los pares de segmentos
    return self.content_minhasher.compute_combined_similarity(
        cv1.minhash_signatures,
        cv2.minhash_signatures
    )
```

**Estrategia de segmentos:**

```
Doc A (largo): [seg1, seg2, seg3]
Doc B (corto): [seg1]

Comparaciones:
  A.seg1 vs B.seg1 → 0.45
  A.seg2 vs B.seg1 → 0.72  ← Máximo
  A.seg3 vs B.seg1 → 0.38

content_sim = 0.72
```

---

## 6. Similaridad de Tópicos (topic_sim)

Usa **divergencia de Jensen-Shannon** entre distribuciones LDA:

$$
JS(P \| Q) = \frac{1}{2} KL(P \| M) + \frac{1}{2} KL(Q \| M)
$$

Donde $M = \frac{1}{2}(P + Q)$ y $KL$ es la divergencia de Kullback-Leibler.

```python
def _compute_topic_similarity(
    self,
    cv1: ContentVector,
    cv2: ContentVector
) -> float:
    """
    Similaridad de tópicos usando Jensen-Shannon.
    """
    if not cv1.topic_distribution or not cv2.topic_distribution:
        return 0.0
    
    return self.lda.compute_topic_similarity(
        cv1.topic_distribution,
        cv2.topic_distribution
    )

# En lda_topics.py
def compute_topic_similarity(
    self, 
    dist1: List[float], 
    dist2: List[float]
) -> float:
    """
    Similaridad = 1 - JS_divergence
    """
    p = np.array(dist1)
    q = np.array(dist2)
    
    # Evitar log(0)
    p = np.clip(p, 1e-10, 1.0)
    q = np.clip(q, 1e-10, 1.0)
    
    # Normalizar
    p = p / p.sum()
    q = q / q.sum()
    
    # Jensen-Shannon
    m = 0.5 * (p + q)
    js_div = 0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m))
    
    # Convertir a similaridad [0, 1]
    return 1.0 - np.sqrt(js_div)
```

---

## 7. Adaptación por Tipo de Documento

El sistema **ajusta los pesos automáticamente** según el tipo de archivo:

```python
# backend/app/core/vectorization/document_vectorizer.py

def _get_adaptive_weights(
    self, 
    filename: str, 
    content: Optional[str]
) -> Tuple[float, float, float]:
    """
    Calcula pesos adaptativos según tipo de documento.
    """
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    # Archivos binarios: peso alto en nombre
    binary_extensions = {'exe', 'dll', 'zip', 'rar', 'jpg', 'png', 'mp3', 'mp4'}
    if extension in binary_extensions or not content:
        return (0.80, 0.00, 0.20)  # name, content, topic
    
    # Código fuente: balance con más contenido
    code_extensions = {'py', 'js', 'ts', 'java', 'cpp', 'go', 'rs'}
    if extension in code_extensions:
        return (0.35, 0.45, 0.20)
    
    # Documentos de texto
    text_extensions = {'txt', 'md', 'rst'}
    if extension in text_extensions:
        return (0.30, 0.50, 0.20)
    
    # Por defecto (PDF, DOCX, etc.)
    return (0.40, 0.40, 0.20)
```

### 7.1 Tabla de Pesos por Tipo

| Categoría | Extensiones | $w_{name}$ | $w_{content}$ | $w_{topic}$ |
|-----------|-------------|------------|---------------|-------------|
| Binario | exe, zip, jpg, mp3 | **0.80** | 0.00 | 0.20 |
| Código | py, js, java, cpp | 0.35 | **0.45** | 0.20 |
| Texto plano | txt, md, rst | 0.30 | **0.50** | 0.20 |
| Documento | pdf, docx, xlsx | 0.40 | 0.40 | 0.20 |

---

## 8. Inferencia de Categoría

La categoría se infiere del nombre del archivo:

```python
# backend/app/core/vectorization/char_ngrams.py

def infer_category(filename: str) -> Dict[str, str]:
    """
    Infiere categoría del documento desde el nombre.
    """
    name_lower = filename.lower()
    category = {}
    
    # Inferir dominio
    domain_patterns = {
        'finanzas': ['ventas', 'factura', 'balance', 'presupuesto', 'fiscal'],
        'rrhh': ['nomina', 'empleado', 'contrato', 'vacaciones', 'personal'],
        'legal': ['contrato', 'acuerdo', 'demanda', 'sentencia', 'ley'],
        'tecnico': ['manual', 'guia', 'especificacion', 'requisito', 'api'],
        'marketing': ['campana', 'publicidad', 'leads', 'conversion', 'roi']
    }
    
    for domain, keywords in domain_patterns.items():
        if any(kw in name_lower for kw in keywords):
            category['domain'] = domain
            break
    
    # Inferir tipo de documento
    type_patterns = {
        'reporte': ['reporte', 'report', 'informe'],
        'factura': ['factura', 'invoice', 'recibo'],
        'contrato': ['contrato', 'contract', 'acuerdo'],
        'manual': ['manual', 'guia', 'guide', 'tutorial'],
        'presentacion': ['presentacion', 'ppt', 'slides']
    }
    
    for doc_type, keywords in type_patterns.items():
        if any(kw in name_lower for kw in keywords):
            category['type'] = doc_type
            break
    
    # Detectar patrón temporal
    import re
    if re.search(r'Q[1-4][-_]?\d{4}|20\d{2}[-_]?Q[1-4]', filename):
        match = re.search(r'(Q[1-4])[-_]?(\d{4})|(\d{4})[-_]?(Q[1-4])', filename)
        if match:
            quarter = match.group(1) or match.group(4)
            year = match.group(2) or match.group(3)
            category['temporal'] = f"{quarter}-{year}"
    
    return category
```

---

## 9. Ejemplo Completo de Vectorización

```python
# Documento: "ReporteVentas_Q1_2024.xlsx"
# Contenido: "Las ventas del primer trimestre mostraron crecimiento..."

vector = vectorizer.vectorize(
    filename="ReporteVentas_Q1_2024.xlsx",
    content="Las ventas del primer trimestre mostraron crecimiento..."
)

# Resultado:
DocumentVector(
    name_vector=NameVector(
        tokens_tfidf={
            "reporte": 0.34,
            "ventas": 0.52,
            "q1": 0.71,
            "2024": 0.28
        },
        char_ngrams_signature=[4521, 8723, 1234, ...],  # 128 valores
        category={
            "domain": "finanzas",
            "type": "reporte",
            "temporal": "Q1-2024"
        }
    ),
    content_vector=ContentVector(
        minhash_signatures=[[2341, 5678, ...], [3456, 7890, ...]],
        keywords_textrank=["ventas", "trimestre", "crecimiento"],
        topic_distribution=[0.02, 0.01, 0.45, 0.03, ...]  # 20 tópicos
    ),
    structural_features=StructuralFeatures(
        extension="xlsx",
        name_length=24,
        has_date_pattern=True,
        has_version=False
    ),
    name_weight=0.40,
    content_weight=0.40,
    topic_weight=0.20
)
```

---

## 10. Desglose de Similaridad

Para debugging, se puede obtener el desglose completo:

```python
breakdown = vectorizer.get_similarity_breakdown(vec1, vec2)

# Resultado:
{
    'name_similarity': 0.78,
    'content_similarity': 0.65,
    'topic_similarity': 0.82,
    'total_similarity': 0.73,  # 0.4*0.78 + 0.4*0.65 + 0.2*0.82
    'weights': {
        'name': 0.4,
        'content': 0.4,
        'topic': 0.2
    }
}
```

---

> **Anterior**: [02_MinHash_LSH.md](02_MinHash_LSH.md)
> 
> **Siguiente**: [04_LDA_Topicos_Locales.md](04_LDA_Topicos_Locales.md)