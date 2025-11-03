# SSDD - Chord DHT (Tabla Hash Distribuida)

# Nota Final : 7

## Parcipantes:

<table>
  <tr>
    <td align="center"><a href="https://github.com/AnOrdinaryUsser"><img width="100px;" src="https://avatars2.githubusercontent.com/u/61872281?s=460&u=e276002ebcb7a49338dac7ffb561cf968d6c0ee4&v=4"></td>
    <td align="center"><a href="https://github.com/n0nuser"><img width="100px;" src="https://avatars3.githubusercontent.com/u/32982175?s=460&u=ce93410c9c5e0f3ffa17321e16ee2f2b8879ca6f&v=4"></td>
  </tr>
</table>

## Un poco sobre CHORD

Chord es un protocolo y algoritmo para una tabla hash distribuida punto a punto que se puede utilizar para compartir archivos entre pares (p2p). El algoritmo Chord es el encargado de distribuir objetos en un red dinámica y es el quien implementa un protocolo para encontrar esos objetos en la red. Además la ubicación de los datos se implementa en la parte superior de Chord al asociar una clave con cada elemento de datos y almacenar el par clave/elemento de datos en el nodo al que asigna la clave.

El protocolo Chord admite solo una operación: dada una clave, determina el nodo responsable de almacenar el valor de la clave.

Cada clave (basada en el nombre del archivo) insertada en el DHT se codifica para encajar en el espacio de teclas admitido por la implementación particular de Chord. El espacio de claves (el rango de hashes posibles), en esta implementación reside entre 0 y 2 m-1 inclusive donde m = 10 (indicado por MAX_BITS en el código). Así que el espacio de claves está entre 0 y 1023.

Los nodos así como las claves también tienen un valor hash en la DHT que es el que hemos construido a traves de la combinación de su IP y su PUERTO usando el algoritmo hash SHA1. Tenemos que tener en cuenta los hashes porque Chord ordena los ndos en función de quien es el siguiente hash más alto, y como la red es circular, el nodo sucesor del nodo con el hash más alto será el nodo con el hash más pequeño.

Otro aspecto clave sobre Chord es que es capaz de autoestabilizarse, es decir, si tenemos dos nodos conectados en una red circular y uno de repente se desconecta, como los nodos estan haciendo continuamente ping a su nodo sucesor, los nodos se estabilizarán. Y si pensabamos que los archivos que tenía el nodo que se ha desconectado se pierden, esto no es asñi ya que antes de desconectarse se replican en su nodo sucesor.

## Programa

Dado que Chord es un sistema descentralizado no hay un fichero para el servidor y otro diferente para el cliente, nuestro fichero `peer.py` ya actua como cliente y servidor a nivel del nodo al mismo tiempo.

Este programa ha sido implementado a partir del [código de Nouman Abbasi](https://github.com/MNoumanAbbasi/Chord-DHT-for-File-Sharing). Por otro lado, se ha implementado un servicio API REST con Flask para visualizar mediante peticiones HTTP su funcionamiento, y facilitar la integración con múltiples clientes como puedan ser los buscadores (Firefox, Chrome), u otros programables mediante bots como puedan ser Telegram, Discord, Slack...

## Cómo utilizar el programa

### Poetry

Si queremos utilizar un entorno virtual para las dependencias podemos utilzar Poetry.

Lo primero que tenemos que hacer para poder ejecutar el programa, es crear el entorno virtual para instalar las dependencias en él, y que así no se instalen en nuestro equipo directamente. Para ello primero debemos seleccionar la versión de Python en el que queremos crear el entorno, en este caso la 3.5 pues es la que hay en las aulas:

```
poetry env use python3.5
```

Acto seguido deberemos crear el entorno virtual e instalar las dependencias:

```
poetry install
```

Y ya por último podremos lanzar el comando especificado más abajo para tener un nodo funcionando en nuestro equipo (un nodo por equipo con puerto 2000).

Entonces para hacer la prueba lanzaríamos en 3 terminales de 3 máquinas distintas el siguiente comando:

```
poetry run python3.5 main.py
```

Esto lanzaría una instancia de Flask y se podrían hacer peticiones hacia la IP del equipo al puerto 8080.

### Sin Poetry

Si queremos instalar las dependencias directamente en nuestro equipo podemos lanzar el siguiente comando:

```
pip3 install -r requirements.txt
```

Para ejecutarlo se haría con Python de forma normal:

```
python3.5 main.py
```

## Endpoints

### Añadir nodo

```
http://FLASK_IP:PORT/server/REST/DHT/addNode?ip=IP
```

IP = La IP **de la red** en formato `cadena de texto` (no es aceptada la 127.0.0.1 o localhost) donde te quieres conectar.

### Eliminar nodo

```
http://FLASK_IP:PORT/server/REST/DHT/removeNode
```

### Subir archivo a la red

```
http://FLASK_IP:PORT/server/REST/DHT/uploadContent?filename=NombreFichero&data=Datos
```

- `FILENAME` = NombreDeTuFichero: `notas.txt`
- `DATA` = Una cadena de texto: `Esto es una nota de texto`

### Descargar archivo de la red

```
http://FLASK_IP:PORT/server/REST/DHT/downloadContent?filename=NombreFichero
```

- `FILENAME` = Nombre del fichero subido: `notas.txt`

### Imprimir Finger Table

```
http://FLASK_IP:PORT/server/REST/DHT/imprimirFingerTable
```

### Imprimir sucesor y precedesor

```
http://FLASK_IP:PORT/server/REST/DHT/imprimirSucPred
```
