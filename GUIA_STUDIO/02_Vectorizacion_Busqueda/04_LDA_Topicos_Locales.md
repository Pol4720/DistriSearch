# LDA: Tópicos Locales

## Modelado de Tópicos Entrenado en el Corpus del Cluster

---

## 1. ¿Qué es LDA?

**Latent Dirichlet Allocation (LDA)** es un modelo probabilístico generativo que descubre tópicos latentes en una colección de documentos.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODELO GENERATIVO LDA                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Suposición: Cada documento es una mezcla de tópicos           │
│              Cada tópico es una distribución sobre palabras    │
│                                                                 │
│  Ejemplo con 3 tópicos:                                         │
│                                                                 │
│  Documento "ReporteVentas_Q1.pdf"                               │
│  ├── 45% Tópico 2 (Finanzas): ventas, ingresos, margen, ...   │
│  ├── 35% Tópico 7 (Temporal): trimestre, Q1, período, ...     │
│  └── 20% Tópico 12 (General): reporte, análisis, datos, ...   │
│                                                                 │
│  Distribución de tópicos: [0, 0, 0.45, 0, 0, 0, 0, 0.35, ...]  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ¿Por Qué Entrenamiento Local?

| Modelo Pre-entrenado | LDA Local (DistriSearch) |
|----------------------|--------------------------|
| Tópicos genéricos | Tópicos específicos del corpus |
| No captura jerga interna | Aprende vocabulario de la empresa |
| Tamaño fijo (genérico) | Número de tópicos configurable |
| Requiere descarga ~500MB | Entrenamiento ligero in-situ |
| Actualización costosa | Re-entrena incrementalmente |

### 2.1 Ventajas del Entrenamiento Local

1. **Especificidad**: Los tópicos reflejan exactamente los temas del corpus
2. **Privacidad**: No envía datos a servicios externos
3. **Adaptabilidad**: Evoluciona con el corpus
4. **Eficiencia**: Modelo pequeño (~5MB)

---

## 3. Modelo Matemático

### 3.1 Proceso Generativo

Para cada documento $d$:

1. Elegir distribución de tópicos: $\theta_d \sim \text{Dirichlet}(\alpha)$
2. Para cada palabra $w$ en el documento:
   - Elegir un tópico: $z \sim \text{Multinomial}(\theta_d)$
   - Elegir la palabra: $w \sim \text{Multinomial}(\phi_z)$

### 3.2 Parámetros

- $\alpha$: Prior de Dirichlet para distribución documento-tópico
- $\beta$: Prior de Dirichlet para distribución tópico-palabra
- $K$: Número de tópicos (en DistriSearch: 20 por defecto)

### 3.3 Distribución de Tópicos

La distribución de tópicos para un documento $d$:

$$
P(\text{tópico}_k | d) = \frac{n_{d,k} + \alpha}{\sum_{k'} n_{d,k'} + K\alpha}
$$

Donde $n_{d,k}$ es el número de palabras en $d$ asignadas al tópico $k$.

---

## 4. Implementación en DistriSearch

```python
# backend/app/core/vectorization/lda_topics.py

from gensim import corpora
from gensim.models import LdaModel, LdaMulticore

class LDATopicModeler:
    """
    Modelador de tópicos LDA entrenado localmente.
    """
    
    def __init__(
        self,
        num_topics: int = 20,
        min_word_length: int = 3,
        min_df: int = 5,
        max_df: float = 0.5,
        passes: int = 10,
        random_state: int = 42,
        use_multicore: bool = True
    ):
        """
        Args:
            num_topics: Número de tópicos a extraer
            min_df: Frecuencia mínima de documento para palabras
            max_df: Frecuencia máxima de documento (ratio)
            passes: Pasadas sobre el corpus
        """
        self.num_topics = num_topics
        self.min_df = min_df
        self.max_df = max_df
        self.passes = passes
        self.use_multicore = use_multicore
        
        self._model = None
        self._dictionary = None
        self._is_trained = False
```

### 4.1 Entrenamiento

```python
def train(self, documents: List[str]) -> 'LDATopicModeler':
    """
    Entrena LDA en el corpus local.
    """
    # Preprocesar documentos
    processed_docs = [self._preprocess(doc) for doc in documents]
    processed_docs = [doc for doc in processed_docs if doc]
    
    # Ajustar número de tópicos si hay pocos documentos
    if len(processed_docs) < self.num_topics:
        self.num_topics = max(2, len(processed_docs) // 2)
    
    # Crear diccionario
    self._dictionary = corpora.Dictionary(processed_docs)
    
    # Filtrar extremos
    self._dictionary.filter_extremes(
        no_below=self.min_df,
        no_above=self.max_df
    )
    
    # Crear corpus BOW
    corpus = [self._dictionary.doc2bow(doc) for doc in processed_docs]
    
    # Entrenar LDA
    if self.use_multicore:
        self._model = LdaMulticore(
            corpus=corpus,
            id2word=self._dictionary,
            num_topics=self.num_topics,
            passes=self.passes,
            random_state=self.random_state,
            workers=2
        )
    else:
        self._model = LdaModel(
            corpus=corpus,
            id2word=self._dictionary,
            num_topics=self.num_topics,
            passes=self.passes,
            random_state=self.random_state
        )
    
    self._is_trained = True
    return self
```

---

## 5. Obtener Distribución de Tópicos

```python
def get_topic_distribution(self, text: str) -> List[float]:
    """
    Obtiene distribución de tópicos para un documento.
    
    Retorna: Lista de probabilidades [p_0, p_1, ..., p_{K-1}]
    """
    if not self._is_trained:
        # Distribución uniforme si no está entrenado
        return [1.0 / self.num_topics] * self.num_topics
    
    # Preprocesar
    tokens = self._preprocess(text)
    
    if not tokens:
        return [1.0 / self.num_topics] * self.num_topics
    
    # Convertir a BOW
    bow = self._dictionary.doc2bow(tokens)
    
    if not bow:
        return [1.0 / self.num_topics] * self.num_topics
    
    # Obtener distribución
    topic_dist = self._model.get_document_topics(
        bow, 
        minimum_probability=0.0
    )
    
    # Convertir a lista de tamaño fijo
    distribution = [0.0] * self.num_topics
    for topic_id, prob in topic_dist:
        if topic_id < self.num_topics:
            distribution[topic_id] = prob
    
    return distribution
```

### 5.1 Ejemplo de Distribución

```python
# Documento sobre ventas
text = """
Las ventas del primer trimestre superaron las expectativas.
El margen operativo creció un 15% respecto al año anterior.
Los ingresos totales alcanzaron $2.5 millones.
"""

distribution = lda.get_topic_distribution(text)

# Resultado (20 tópicos):
# [0.02, 0.01, 0.45, 0.03, 0.02, 0.01, 0.08, 0.12, ...]
#              ^^^^                          ^^^^
#        Tópico "Finanzas"           Tópico "Temporal"
```

---

## 6. Similaridad de Tópicos: Jensen-Shannon

La **divergencia de Jensen-Shannon** mide qué tan diferentes son dos distribuciones:

$$
JS(P \| Q) = \frac{1}{2} D_{KL}(P \| M) + \frac{1}{2} D_{KL}(Q \| M)
$$

Donde:
- $M = \frac{1}{2}(P + Q)$ es la distribución promedio
- $D_{KL}$ es la divergencia de Kullback-Leibler:

$$
D_{KL}(P \| Q) = \sum_i P_i \log\frac{P_i}{Q_i}
$$

### 6.1 Implementación

```python
def compute_topic_similarity(
    self, 
    dist1: List[float], 
    dist2: List[float]
) -> float:
    """
    Similaridad = 1 - sqrt(JS_divergence)
    
    JS está acotada en [0, 1], por lo que similaridad también.
    """
    import numpy as np
    
    p = np.array(dist1)
    q = np.array(dist2)
    
    # Evitar log(0)
    p = np.clip(p, 1e-10, 1.0)
    q = np.clip(q, 1e-10, 1.0)
    
    # Normalizar (por si acaso)
    p = p / p.sum()
    q = q / q.sum()
    
    # Distribución promedio
    m = 0.5 * (p + q)
    
    # Jensen-Shannon divergence
    js_div = 0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m))
    
    # Convertir a similaridad [0, 1]
    # sqrt porque JS está en [0, log(2)] para distribuciones discretas
    return 1.0 - np.sqrt(js_div / np.log(2))
```

### 6.2 Ejemplo de Similaridad

```
Documento A (Finanzas): [0.02, 0.01, 0.45, 0.03, ...]
Documento B (Finanzas): [0.03, 0.02, 0.42, 0.05, ...]
Documento C (Legal):    [0.01, 0.50, 0.02, 0.01, ...]

JS(A, B) = 0.03 → Similaridad = 0.97 (muy similares)
JS(A, C) = 0.45 → Similaridad = 0.33 (diferentes)
```

---

## 7. Visualización de Tópicos

```python
def get_top_words(
    self, 
    topic_id: int, 
    n_words: int = 10
) -> List[Tuple[str, float]]:
    """
    Obtiene las palabras más representativas de un tópico.
    """
    if not self._is_trained or topic_id >= self.num_topics:
        return []
    
    return self._model.show_topic(topic_id, n_words)
```

### 7.1 Ejemplo de Tópicos Descubiertos

```
Tópico 0 (Tecnología):
  software: 0.082, sistema: 0.065, datos: 0.058, 
  aplicacion: 0.045, servidor: 0.042, ...

Tópico 2 (Finanzas):
  ventas: 0.095, ingresos: 0.078, margen: 0.062,
  balance: 0.055, fiscal: 0.048, ...

Tópico 5 (RRHH):
  empleado: 0.088, nomina: 0.072, contrato: 0.065,
  vacaciones: 0.052, personal: 0.048, ...

Tópico 8 (Legal):
  contrato: 0.092, clausula: 0.075, partes: 0.068,
  obligacion: 0.055, demanda: 0.045, ...
```

---

## 8. Persistencia del Modelo

```python
def save(self, path: str):
    """Guarda modelo entrenado."""
    import os
    os.makedirs(path, exist_ok=True)
    
    if self._model:
        self._model.save(os.path.join(path, 'lda.model'))
    if self._dictionary:
        self._dictionary.save(os.path.join(path, 'dictionary.dict'))

def load(self, path: str) -> 'LDATopicModeler':
    """Carga modelo entrenado."""
    import os
    
    model_path = os.path.join(path, 'lda.model')
    dict_path = os.path.join(path, 'dictionary.dict')
    
    if os.path.exists(model_path):
        self._model = LdaModel.load(model_path)
    if os.path.exists(dict_path):
        self._dictionary = corpora.Dictionary.load(dict_path)
    
    self._is_trained = True
    return self
```

---

## 9. Re-entrenamiento Incremental

Cuando llegan nuevos documentos:

```python
def update(self, new_documents: List[str]):
    """
    Actualiza modelo con nuevos documentos.
    """
    processed = [self._preprocess(doc) for doc in new_documents]
    processed = [doc for doc in processed if doc]
    
    # Actualizar diccionario
    self._dictionary.add_documents(processed)
    
    # Crear corpus para nuevos documentos
    new_corpus = [self._dictionary.doc2bow(doc) for doc in processed]
    
    # Actualizar modelo (online learning)
    self._model.update(new_corpus)
```

---

## 10. Inferencia de Tópicos desde Nombre

Para archivos binarios sin contenido extraíble:

```python
def infer_topics_from_name(
    self, 
    filename_tokens: List[str]
) -> List[float]:
    """
    Infiere tópicos solo del nombre del archivo.
    
    Útil para archivos binarios (exe, zip, jpg, etc.)
    """
    if not self._is_trained or not filename_tokens:
        return [1.0 / self.num_topics] * self.num_topics
    
    # Expandir tokens del nombre con sinónimos conocidos
    expanded_tokens = self._expand_tokens(filename_tokens)
    
    # Obtener distribución
    bow = self._dictionary.doc2bow(expanded_tokens)
    
    if not bow:
        return [1.0 / self.num_topics] * self.num_topics
    
    topic_dist = self._model.get_document_topics(bow, minimum_probability=0.0)
    
    distribution = [0.0] * self.num_topics
    for topic_id, prob in topic_dist:
        distribution[topic_id] = prob
    
    return distribution
```

---

## 11. Flujo Completo

```
┌─────────────────────────────────────────────────────────────────┐
│                 PIPELINE LDA EN DISTRISEARCH                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ENTRENAMIENTO (una vez, al iniciar cluster)                │
│     ├── Recopilar todos los documentos del corpus              │
│     ├── Preprocesar (tokenizar, filtrar stopwords)             │
│     ├── Entrenar LDA con K=20 tópicos                          │
│     └── Guardar modelo en disco                                 │
│                                                                 │
│  2. VECTORIZACIÓN (por documento)                               │
│     ├── Cargar modelo entrenado                                 │
│     ├── Preprocesar contenido del documento                     │
│     ├── Convertir a BOW                                         │
│     └── Obtener distribución de tópicos [p₀, p₁, ..., p₁₉]     │
│                                                                 │
│  3. BÚSQUEDA                                                    │
│     ├── Query → distribución de tópicos                         │
│     ├── Comparar con docs usando Jensen-Shannon                 │
│     └── Contribuye 20% a la similaridad total                   │
│                                                                 │
│  4. ACTUALIZACIÓN (periódica)                                   │
│     ├── Nuevos documentos llegan                                │
│     └── Actualización incremental del modelo                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Resumen de Parámetros

| Parámetro | Valor Default | Descripción |
|-----------|---------------|-------------|
| `num_topics` | 20 | Número de tópicos latentes |
| `passes` | 10 | Pasadas de entrenamiento |
| `min_df` | 5 | Frecuencia mínima de documento |
| `max_df` | 0.5 | Frecuencia máxima (50% de docs) |
| `alpha` | auto | Prior documento-tópico |
| `eta` | auto | Prior tópico-palabra |

---

> **Anterior**: [03_Vector_Caracteristico_Adaptativo.md](03_Vector_Caracteristico_Adaptativo.md)
> 
> **Siguiente sección**: [../03_Particionamiento/README.md](../03_Particionamiento/README.md)