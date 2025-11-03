import socket
from peer import Peer
from flask import Flask, request

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
IP = s.getsockname()[0]
PORT = 2000
BUFFER = 4096
MAX_BITS = 10

api = Flask(__name__)
peer = Peer(IP, PORT, BUFFER, MAX_BITS)
peer.start()


@api.route("/server/rest/DHT/addNode")
def anadirNodo():
    """
    Se encarga de agregar el nodo existente a la red que se le pase por argumento
    """
    global peer, IP
    ip = request.args.get("ip")
    if ip:
        if ip == "127.0.0.1" or ip == "localhost":
            return "La IP no es válida. Sólo se acepta la IP en red del equipo."
        peer.unirseRed(ip, PORT)
        return (
            "Se ha unido el nodo ("
            + str(IP)
            + ":"
            + str(PORT)
            + ") con ID "
            + str(peer.id)
            + " a la red "
            + str(ip)
        )
    else:
        return "No se ha podido unir al nodo a la red. Falta la IP."


@api.route("/server/rest/DHT/removeNode")
def apagarNodo():
    """
    Se encarga de abandonar la red.
    """
    global peer
    if peer:
        peer.abandonarRed()
        text = "Cerrando nodo con id: " + str(peer.id)
        return text
    else:
        return "El nodo ya se encuentra apagado."


@api.route("/server/rest/DHT/uploadContent")
def subirArchivo():
    """
    Se encarga de subir un archivo a la red.
    """
    global peer
    if peer:
        filename = request.args.get("filename")
        data = request.args.get("data")
        if filename and data:
            fileID = peer.hashFichero(filename)
            recvIPport = peer.sucesorDHT(peer.sucesor, fileID)
            peer.subirFichero(filename, data, recvIPport, True)
            return (
                "Se ha subido el archivo " + str(filename) + " con el id " + str(fileID)
            )
        else:
            return "Faltan parámetros de URL: filename, data."
    else:
        return "No se ha iniciado el nodo."


@api.route("/server/rest/DHT/downloadContent")
def descargarArchivo():
    """
    Se encarga de descargar un archivo de la red.
    """
    global peer
    if peer:
        filename = request.args.get("filename")
        if filename:
            peer.descargarFichero(filename)
            text = "Archivo " + filename + " descargado.<br>"
            with open(filename, "r") as f:
                data = f.readlines()
            for line in data:
                text += line + "<br>"
            return text
        else:
            return "Faltan párametros de URL: filename."
    else:
        return "No se ha iniciado el nodo."


@api.route("/server/rest/DHT/imprimirFingerTable")
def imprimirFingerTable():
    """
    Se encarga de imprimir la lista de hashes.
    """
    global peer
    if peer:
        return peer.mostrarFingerTable()
    else:
        return "No se ha iniciado el nodo."


@api.route("/server/rest/DHT/imprimirSucPred")
def imprimirSucPred():
    """
    Se encarga de imprimir el sucesor y el predecesor.
    """
    global peer
    if peer:
        text = "ID: " + str(peer.id) + "<br>"
        text = text + "Suc: " + str(peer.sucesorID) + "<br>"
        text = text + "Pred: " + str(peer.predecesorID) + "<br>"
        return text
    else:
        return "No se ha iniciado el nodo."


try:
    api.run(host="0.0.0.0", port=8080)
except Exception as e:
    peer.socketListener.close()
