# Sistema de Vectorización Adaptativa

## Búsqueda Semántica sin Embeddings Pre-entrenados

---

## 1. Visión General

DistriSearch implementa un **sistema de vectorización adaptativo** que NO depende de embeddings pre-entrenados de dimensión fija. Esta decisión de diseño resuelve problemas críticos con documentos extensos.

```
┌─────────────────────────────────────────────────────────────────┐
│              PIPELINE DE VECTORIZACIÓN                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────┐       │
│  │ Documento│───▶│ Preprocesado │───▶│ Vectorización   │       │
│  │ (entrada)│    │ (tokenización│    │ Multi-nivel     │       │
│  └──────────┘    │  limpieza)   │    └────────┬────────┘       │
│                  └──────────────┘             │                 │
│                                               ▼                 │
│  ┌────────────────────────────────────────────────────────────┐│
│  │           VECTOR CARACTERÍSTICO ADAPTATIVO                 ││
│  ├────────────────────────────────────────────────────────────┤│
│  │  Nivel 1: Nombre (TF-IDF + N-gramas)     peso: 40%        ││
│  │  Nivel 2: Contenido (MinHash + Keywords)  peso: 40%        ││
│  │  Nivel 3: Tópicos (LDA local)             peso: 20%        ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. ¿Por Qué No Usar Embeddings Pre-entrenados?

| Problema con Embeddings Fijos | Solución en DistriSearch |
|-------------------------------|--------------------------|
| Dimensión fija (768, 1024) | Vectores sparse adaptativos |
| Pérdida de información en docs largos | Segmentación con MinHash |
| Modelos pesados (>500MB) | LDA ligero entrenado localmente |
| Vocabulario genérico | TF-IDF específico del corpus |
| Costosos en GPU | CPU-friendly |

---

## 3. Componentes del Sistema

### 3.1 Estructura de Directorios

```
backend/app/core/vectorization/
├── document_vectorizer.py   # 🔴 Clase principal
├── tfidf_processor.py       # TF-IDF jerárquico
├── minhash_signature.py     # MinHash + LSH
├── lda_topics.py            # LDA local
├── textrank_keywords.py     # Extracción de keywords
├── char_ngrams.py           # N-gramas de caracteres
└── __init__.py
```

### 3.2 Clase Principal: DocumentVectorizer

```python
# backend/app/core/vectorization/document_vectorizer.py
class DocumentVectorizer:
    """
    Vectorizador Adaptativo de Documentos.
    
    Computa vectores multi-nivel:
    - Nivel 1: Vector del nombre (TF-IDF + char n-grams + categoría)
    - Nivel 2: Vector de contenido (MinHash + TextRank + LDA)
    - Nivel 3: Features estructurales (extensión, tamaño, patrones)
    """
    
    def __init__(
        self,
        minhash_num_perm: int = 128,
        lda_num_topics: int = 20,
        tfidf_max_features: int = 5000,
        name_weight: float = 0.4,
        content_weight: float = 0.4,
        topic_weight: float = 0.2
    ):
        # Inicializa procesadores
        self.filename_tfidf = FilenameTFIDFProcessor()
        self.content_tfidf = TFIDFProcessor()
        self.minhash = MinHashSignature(num_perm=minhash_num_perm)
        self.lda = LDATopicModeler(num_topics=lda_num_topics)
        self.keyword_extractor = TextRankKeywordExtractor()
        self.char_ngram = CharNGramProcessor()
```

---

## 4. Flujo de Vectorización

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESO DE VECTORIZACIÓN                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. ENTRADA                                                     │
│     ├── filename: "ReporteVentas_Q1_2024.xlsx"                 │
│     └── content: "Las ventas del primer trimestre..."          │
│                                                                 │
│  2. NIVEL 1 - NOMBRE                                            │
│     ├── Tokenizar: ["reporte", "ventas", "q1", "2024"]         │
│     ├── TF-IDF: {"reporte": 0.34, "ventas": 0.52, ...}         │
│     ├── N-gramas: ["re", "ep", "po", "rep", "epo", ...]        │
│     └── Categoría: {domain: "finanzas", type: "reporte"}       │
│                                                                 │
│  3. NIVEL 2 - CONTENIDO                                         │
│     ├── Segmentar documento (chunks de 1000 tokens)            │
│     ├── MinHash por segmento: [[sig1], [sig2], ...]            │
│     ├── TextRank keywords: ["ventas", "trimestre", ...]        │
│     └── LDA topics: [0.02, 0.45, 0.12, ...]                    │
│                                                                 │
│  4. NIVEL 3 - ESTRUCTURA                                        │
│     ├── extension: ".xlsx"                                      │
│     ├── has_date_pattern: true                                  │
│     └── section_count: 5                                        │
│                                                                 │
│  5. SALIDA: DocumentVector                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Cálculo de Similaridad

La similaridad entre documentos se calcula como combinación ponderada:

$$
\text{Similaridad} = w_{\text{name}} \cdot S_{\text{name}} + w_{\text{content}} \cdot S_{\text{content}} + w_{\text{topic}} \cdot S_{\text{topic}}
$$

Donde por defecto: $w_{\text{name}} = 0.4$, $w_{\text{content}} = 0.4$, $w_{\text{topic}} = 0.2$

```python
def compute_similarity(self, vec1: DocumentVector, vec2: DocumentVector) -> float:
    name_sim = self._compute_name_similarity(vec1.name_vector, vec2.name_vector)
    content_sim = self._compute_content_similarity(vec1.content_vector, vec2.content_vector)
    topic_sim = self._compute_topic_similarity(vec1.content_vector, vec2.content_vector)
    
    return (
        self.name_weight * name_sim +
        self.content_weight * content_sim +
        self.topic_weight * topic_sim
    )
```

---

## 6. Adaptación por Tipo de Documento

El sistema ajusta pesos según el tipo de documento:

| Tipo de Archivo | $w_{\text{name}}$ | $w_{\text{content}}$ | $w_{\text{topic}}$ |
|-----------------|-------------------|----------------------|--------------------|
| Binario (.exe, .zip) | 0.80 | 0.00 | 0.20 |
| Texto (.txt, .md) | 0.30 | 0.50 | 0.20 |
| Documento (.pdf, .docx) | 0.40 | 0.40 | 0.20 |
| Código (.py, .js) | 0.35 | 0.45 | 0.20 |

---

## 7. Índice de Contenidos

| Archivo | Descripción |
|---------|-------------|
| [01_TF_IDF_Jerarquico.md](01_TF_IDF_Jerarquico.md) | TF-IDF con pesos por nivel |
| [02_MinHash_LSH.md](02_MinHash_LSH.md) | Similaridad Jaccard eficiente |
| [03_Vector_Caracteristico_Adaptativo.md](03_Vector_Caracteristico_Adaptativo.md) | Estructura del vector multi-nivel |
| [04_LDA_Topicos_Locales.md](04_LDA_Topicos_Locales.md) | Modelado de tópicos local |

---

> **Anterior**: [../01_Arquitectura_General/README.md](../01_Arquitectura_General/README.md)
> 
> **Siguiente**: [01_TF_IDF_Jerarquico.md](01_TF_IDF_Jerarquico.md)