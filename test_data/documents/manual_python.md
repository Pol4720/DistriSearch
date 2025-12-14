# Manual Básico de Python

## Introducción

Python es un lenguaje de programación interpretado, de alto nivel y propósito general.
Su filosofía de diseño enfatiza la legibilidad del código con el uso de indentación significativa.

## Variables y Tipos de Datos

```python
# Números
entero = 42
flotante = 3.14159
complejo = 3 + 4j

# Cadenas
texto = "Hola, mundo"
multilinea = """Este es un texto
que ocupa varias líneas"""

# Listas
lista = [1, 2, 3, 4, 5]

# Diccionarios
diccionario = {"nombre": "Python", "version": 3.11}
```

## Estructuras de Control

### Condicionales
```python
if condicion:
    hacer_algo()
elif otra_condicion:
    hacer_otra_cosa()
else:
    hacer_default()
```

### Bucles
```python
for elemento in lista:
    print(elemento)

while condicion:
    ejecutar()
```

## Funciones

```python
def saludar(nombre):
    return f"Hola, {nombre}!"
```

## Clases

```python
class Persona:
    def __init__(self, nombre):
        self.nombre = nombre
    
    def presentarse(self):
        return f"Me llamo {self.nombre}"
```
