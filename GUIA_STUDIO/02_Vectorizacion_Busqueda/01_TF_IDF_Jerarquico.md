# TF-IDF Jerárquico

## Representación Vectorial en Tres Niveles

---

## 1. ¿Qué es TF-IDF?

**TF-IDF** (Term Frequency - Inverse Document Frequency) es una técnica estadística para evaluar la importancia de una palabra en un documento dentro de un corpus.

### 1.1 Fórmulas Matemáticas

**Term Frequency (TF)** - Frecuencia normalizada del término en el documento:

$$
TF(t,d) = \frac{f_{t,d}}{\sum_{t' \in d} f_{t',d}}
$$

Donde:
- $f_{t,d}$ = número de veces que el término $t$ aparece en el documento $d$
- $\sum_{t' \in d} f_{t',d}$ = total de términos en el documento

**Inverse Document Frequency (IDF)** - Penaliza términos muy comunes:

$$
IDF(t) = \log\frac{N}{|\{d \in D : t \in d\}|}
$$

Donde:
- $N$ = número total de documentos en el corpus
- $|\{d \in D : t \in d\}|$ = documentos que contienen el término $t$

**TF-IDF combinado**:

$$
TFIDF(t,d) = TF(t,d) \times IDF(t)
$$

---

## 2. ¿Por Qué TF-IDF Jerárquico?

En DistriSearch, aplicamos TF-IDF en **tres niveles** con diferentes propósitos:

```
┌─────────────────────────────────────────────────────────────────┐
│                   TF-IDF JERÁRQUICO                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  NIVEL 1: NOMBRE DEL ARCHIVO (Alta Prioridad)                  │
│  ├── TF-IDF sobre tokens del nombre                            │
│  ├── N-gramas de caracteres (2,3,4)                            │
│  └── Peso: 40% en similaridad final                            │
│                                                                 │
│  NIVEL 2: CONTENIDO (Segmentado)                               │
│  ├── TF-IDF sobre contenido completo                           │
│  ├── Keywords extraídos con TextRank                           │
│  └── Peso: 40% en similaridad final                            │
│                                                                 │
│  NIVEL 3: METADATOS ESTRUCTURALES                              │
│  ├── Extensión del archivo                                     │
│  ├── Patrones detectados (fechas, versiones)                   │
│  └── Contribuye a categorización                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Implementación: TFIDFProcessor

```python
# backend/app/core/vectorization/tfidf_processor.py

class TFIDFProcessor:
    """
    Procesador TF-IDF para vectorización de texto.
    """
    
    def __init__(
        self,
        max_features: int = 5000,
        min_df: int = 1,
        max_df: float = 0.95,
        ngram_range: Tuple[int, int] = (1, 2),
        use_idf: bool = True,
        smooth_idf: bool = True,
        sublinear_tf: bool = True,  # Usa 1 + log(tf)
        lowercase: bool = True
    ):
        self._vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=min_df,
            max_df=max_df,
            ngram_range=ngram_range,
            use_idf=use_idf,
            smooth_idf=smooth_idf,
            sublinear_tf=sublinear_tf,
            lowercase=lowercase,
            token_pattern=r'(?u)\b\w+\b',
            strip_accents='unicode'
        )
```

### 3.1 Sublinear TF

Cuando `sublinear_tf=True`, se aplica escalado logarítmico:

$$
TF_{sublinear}(t,d) = 1 + \log(f_{t,d})
$$

Esto evita que términos muy frecuentes dominen el vector.

---

## 4. Nivel 1: Vector del Nombre

El nombre del archivo tiene **alta prioridad** porque:
- Siempre está disponible (incluso para archivos binarios)
- Contiene semántica clave elegida por el usuario
- Es corto y específico

### 4.1 Procesamiento del Nombre

```python
# backend/app/core/vectorization/tfidf_processor.py

class FilenameTFIDFProcessor(TFIDFProcessor):
    """TF-IDF especializado para nombres de archivo."""
    
    def preprocess_filename(self, filename: str) -> str:
        """
        Preprocesa nombre de archivo.
        
        Ejemplo: "ReporteVentas_Q1_2024.xlsx"
        Resultado: "reporte ventas q1 2024 reporteventas"
        """
        # Remover extensión
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        
        # Separar por caracteres especiales
        tokens = re.split(r'[_\-\s\.]+', name)
        
        # Agregar nombre sin separadores (para coincidencias parciales)
        tokens.append(re.sub(r'[_\-\s\.]+', '', name.lower()))
        
        return ' '.join(tokens).lower()
```

### 4.2 N-gramas de Caracteres

Capturan errores tipográficos y variantes:

```python
# backend/app/core/vectorization/char_ngrams.py

class CharNGramProcessor:
    """Procesador de N-gramas de caracteres."""
    
    def __init__(self, ngram_sizes: List[int] = [2, 3, 4]):
        self.ngram_sizes = ngram_sizes
    
    def get_ngrams(self, text: str) -> Set[str]:
        """
        Ejemplo: "ventas" con n=3
        Resultado: {"^ve", "ven", "ent", "nta", "tas", "as$"}
        """
        text = f'^{text.lower()}$'  # Marcadores de inicio/fin
        ngrams = set()
        
        for n in self.ngram_sizes:
            ngrams.update(
                text[i:i+n] for i in range(len(text) - n + 1)
            )
        
        return ngrams
```

**Ejemplo de similaridad con n-gramas:**

```
"ventas" vs "bentas" (error tipográfico)

N-gramas de "ventas": {^ve, ven, ent, nta, tas, as$, ^ven, vent, enta, ntas, tas$, ...}
N-gramas de "bentas": {^be, ben, ent, nta, tas, as$, ^ben, bent, enta, ntas, tas$, ...}

Intersección: {ent, nta, tas, as$, enta, ntas, tas$, ...}

Jaccard = |intersección| / |unión| ≈ 0.75 (alta similaridad)
```

---

## 5. Nivel 2: Vector de Contenido

Para documentos extensos, aplicamos TF-IDF al contenido completo:

```python
def fit(self, documents: List[str]) -> 'TFIDFProcessor':
    """
    Entrena el vectorizador en un corpus.
    """
    valid_docs = [doc for doc in documents if doc and doc.strip()]
    
    self._vectorizer.fit(valid_docs)
    self._vocabulary = self._vectorizer.vocabulary_
    self._idf_values = self._vectorizer.idf_
    self._is_fitted = True
    
    return self

def get_tfidf_dict(self, text: str) -> Dict[str, float]:
    """
    Obtiene pesos TF-IDF como diccionario.
    
    Ejemplo salida:
    {"ventas": 0.52, "trimestre": 0.48, "crecimiento": 0.35}
    """
    vector = self._vectorizer.transform([text])
    feature_names = self._vectorizer.get_feature_names_out()
    
    # Convertir sparse matrix a diccionario
    result = {}
    for idx in vector.nonzero()[1]:
        result[feature_names[idx]] = vector[0, idx]
    
    return result
```

---

## 6. Nivel 3: Metadatos Estructurales

Extraemos patrones del nombre y estructura:

```python
# backend/app/core/vectorization/document_vectorizer.py

def _compute_structural_features(self, filename: str, ...) -> StructuralFeatures:
    """Extrae features estructurales."""
    
    return StructuralFeatures(
        extension=filename.rsplit('.', 1)[1].lower(),
        name_length=len(filename),
        has_date_pattern=bool(re.search(r'\d{4}|Q[1-4]', filename)),
        has_version=bool(re.search(r'v\d+|version', filename, re.I)),
        section_count=len(re.findall(r'^#{1,6}', content, re.MULTILINE)),
        has_tables=bool(re.search(r'\|.*\|.*\|', content))
    )
```

---

## 7. Ventajas vs Embeddings de Dimensión Fija

| Aspecto | Embeddings Fijos | TF-IDF Jerárquico |
|---------|------------------|-------------------|
| **Dimensión** | Fija (768, 1024) | Sparse, variable |
| **Docs largos** | Trunca o promedia | Preserva todo |
| **Vocabulario** | Pre-entrenado genérico | Específico del corpus |
| **Memoria** | ~500MB por modelo | ~50MB vocabulario |
| **Interpretabilidad** | Opaco | Claro (términos con pesos) |
| **Actualización** | Re-entrenamiento costoso | Incremental fácil |

---

## 8. Ejemplo Completo

```python
# Vectorización de "ReporteVentas_Q1_2024.xlsx"

# NIVEL 1: Nombre
name_tokens = ["reporte", "ventas", "q1", "2024"]
name_tfidf = {
    "reporte": 0.34,
    "ventas": 0.52,      # Alta importancia
    "q1": 0.71,          # Muy específico (bajo DF)
    "2024": 0.28
}
char_ngrams = {"rep", "epo", "por", "ort", "rte", "ven", "ent", "nta", "tas", ...}
category = {"domain": "finanzas", "type": "reporte", "temporal": "Q1-2024"}

# NIVEL 2: Contenido (si extraíble)
content_tfidf = {
    "ventas": 0.45,
    "trimestre": 0.38,
    "crecimiento": 0.32,
    "margen": 0.28,
    ...
}
keywords_textrank = ["ventas", "trimestre", "crecimiento", "margen", "operativo"]

# NIVEL 3: Estructura
structural = {
    "extension": "xlsx",
    "has_date_pattern": True,
    "has_version": False
}
```

---

## 9. Similaridad con Coseno

Para comparar vectores TF-IDF usamos **similaridad del coseno**:

$$
\cos(\vec{A}, \vec{B}) = \frac{\vec{A} \cdot \vec{B}}{|\vec{A}| \times |\vec{B}|}
$$

```python
def compute_similarity_from_dicts(
    self, 
    dict1: Dict[str, float], 
    dict2: Dict[str, float]
) -> float:
    """Coseno entre dos vectores sparse (diccionarios)."""
    
    common_terms = set(dict1.keys()) & set(dict2.keys())
    
    if not common_terms:
        return 0.0
    
    dot_product = sum(dict1[t] * dict2[t] for t in common_terms)
    norm1 = math.sqrt(sum(v**2 for v in dict1.values()))
    norm2 = math.sqrt(sum(v**2 for v in dict2.values()))
    
    return dot_product / (norm1 * norm2)
```

---

> **Anterior**: [README.md](README.md)
> 
> **Siguiente**: [02_MinHash_LSH.md](02_MinHash_LSH.md)