"""
Tokenizador y procesamiento de texto.
"""
import re
from typing import List, Set

# Stopwords en español
SPANISH_STOPWORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
    'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
    'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
    'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
    'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
    'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
    'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
    'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
    'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
    'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
    'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
    'decir', 'mundo', 'casa', 'último', 'momento', 'tal', 'contra', 'existe'
}


class Tokenizer:
    """Tokenizador simple para texto en español."""
    
    def __init__(self, stopwords: Set[str] = None, min_length: int = 2):
        """
        Args:
            stopwords: Conjunto de stopwords a filtrar
            min_length: Longitud mínima de tokens
        """
        self.stopwords = stopwords or SPANISH_STOPWORDS
        self.min_length = min_length
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokeniza texto en términos.
        
        Proceso:
        1. Minúsculas
        2. Eliminar puntuación
        3. Split por espacios
        4. Filtrar stopwords
        5. Filtrar términos cortos
        
        Args:
            text: Texto a tokenizar
            
        Returns:
            Lista de términos
        """
        # Minúsculas
        text = text.lower()
        
        # Eliminar puntuación (mantener letras, números, espacios)
        text = re.sub(r'[^a-záéíóúñ0-9\s]', ' ', text)
        
        # Split y filtrar
        tokens = [
            token for token in text.split()
            if len(token) >= self.min_length and token not in self.stopwords
        ]
        
        return tokens
    
    def extract_unique_terms(self, text: str) -> Set[str]:
        """
        Extrae términos únicos de un texto.
        
        Args:
            text: Texto a procesar
            
        Returns:
            Conjunto de términos únicos
        """
        return set(self.tokenize(text))


# Instancia global por defecto
_default_tokenizer = Tokenizer()


def tokenize(text: str) -> List[str]:
    """
    Tokeniza texto usando tokenizer por defecto.
    
    Args:
        text: Texto a tokenizar
        
    Returns:
        Lista de términos
    """
    return _default_tokenizer.tokenize(text)


def remove_stopwords(tokens: List[str]) -> List[str]:
    """
    Filtra stopwords de una lista de tokens.
    
    Args:
        tokens: Lista de tokens
        
    Returns:
        Lista de tokens sin stopwords
    """
    return [token for token in tokens if token not in SPANISH_STOPWORDS]


def tokenize_and_filter(text: str) -> List[str]:
    """
    Tokeniza y filtra stopwords en un solo paso.
    
    Args:
        text: Texto a procesar
        
    Returns:
        Lista de términos filtrados
    """
    return tokenize(text)
