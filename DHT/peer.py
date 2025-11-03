import contextlib
from collections import OrderedDict
import threading
import hashlib
import socket
import pickle
import time
import os


class Peer:
    def __init__(self, ip, port, buffer, max_bits):
        self.listaNombresFicheros = []
        self.max_bits = max_bits
        self.max_nodos = 2**max_bits
        self.direccion = (ip, port)
        self.buffer = buffer
        self.id = self.hashFichero(ip + ":" + str(port))
        self.predecesor = (ip, port)  # Predecesor de este nodo
        self.predecesorID = self.id
        self.sucesor = (ip, port)  # Sucesor de este nodo
        self.sucesorID = self.id
        self.fingerTable = OrderedDict()  # {"ID": (IP, port)}

        # Creando los sockets
        # Socket utilizado para escuchar los conexiones entrantes
        try:
            self.socketListener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socketListener.bind(self.direccion)
            self.socketListener.listen()
        except socket.error as e:
            print("No se ha podido abrir el socket: ", e)

    def hashFichero(self, key):
        # Hashea la clave con SHA-1
        resultado = hashlib.sha1(key.encode())
        # Devuelve un entero de 10 bits comprimido
        return int(resultado.hexdigest(), 16) % self.max_nodos

    def listenThread(self):
        # Recoge la petición y manda su información al hilo que la va a manejar
        while True:
            with contextlib.suppress(socket.error):
                conexion, direccion = self.socketListener.accept()
                conexion.settimeout(120)
                threading.Thread(
                    target=self.connectionThread, args=(conexion, direccion)
                ).start()

    # Un hilo para cada petición de un vecino (peer)
    def connectionThread(self, conexion, direccion):
        requestData = pickle.loads(conexion.recv(self.buffer))
        # 5 Tipos de conexiones:
        # Tipo 0: conexion del peer
        # Tipo 1: cliente
        # Tipo 2: ping
        # Tipo 3: búsqueda ID
        # Tipo 4: actualizar sucesor o predecesor
        connectionType = requestData[0]
        if connectionType == 0:
            print("[UNIÓN A LA RED] - ", direccion[0], ":", direccion[1])
            self.unirseNodo(conexion, requestData)
        elif connectionType == 1:
            print("[SUBIDA/BAJADA] - ", direccion[0], ":", direccion[1])
            self.transferFile(conexion, requestData)
        elif connectionType == 2:
            conexion.sendall(pickle.dumps(self.predecesor))
        elif connectionType == 3:
            self.busquedaID(conexion, requestData)
        elif connectionType == 4:
            if requestData[1] == 1:
                self.actualizarSucesor(requestData)
            else:
                self.actualizarPredecesor(requestData)
        elif connectionType == 5:
            self.actualizarFingerTable()
            conexion.sendall(pickle.dumps(self.sucesor))
        else:
            print("Problema con el tipo de conexión")

    def unirseNodo(self, conexion, requestData):
        """
        Gestiona la conexion de otro nodo
        """
        if requestData:
            peerIPport = requestData[1]
            peerID = self.hashFichero(peerIPport[0] + ":" + str(peerIPport[1]))

            # Actualizando el predecesor
            oldPred = self.predecesor
            self.predecesor = peerIPport
            self.predecesorID = peerID

            # Mandando el nuevo predecesor al nodo que se acaba de unir
            socketData = [oldPred]
            conexion.sendall(pickle.dumps(socketData))
            # Actualizando la fingerTable
            time.sleep(0.1)
            self.actualizarFingerTable()
            # Se le pide a los demás nodos que actualizen su fingerTable
            self.updateOtherFTables()

    def transferFile(self, conexion, requestData):
        # Opciones: 0 = Descarga, 1 = Subida
        opcion = requestData[1]
        filename = requestData[2]
        fileID = self.hashFichero(filename)

        # Si el cliente quiere descargar el fichero
        if opcion == 0:
            self._bajarFichero(filename, conexion)
        elif opcion in [1, -1]:
            self._subirFichero(filename, conexion, opcion)

    def _bajarFichero(self, filename, conexion):
        print("Descarga del fichero: ", filename)
        try:
            # Primero busca el fichero en su propio directorio. Si no lo encuentra no lo manda
            if filename not in self.listaNombresFicheros:
                conexion.send("NoEncontrado".encode("utf-8"))
                print("Fichero (" + filename + ") no encontrado")
            # Si encuentra el fichero, lo manda
            else:
                conexion.send("Encontrado".encode("utf-8"))
                self.enviarFichero(conexion, filename)
        except ConnectionResetError as error:
            print(error, "\nCliente desconectado\n\n")

    def _subirFichero(self, filename, conexion, opcion):
        print("Recibiendo el fichero: ", filename)
        fileID = self.hashFichero(filename)
        print("Subiendo el ID del fichero:", fileID)
        self.listaNombresFicheros.append(filename)
        self.receiveFile(conexion, filename)
        print("Subida completada")
        # Replicating file to successor as well
        if opcion == 1 and self.direccion != self.sucesor:
            with open(filename, "r") as f:
                data = f.read()
            self.subirFichero(filename, data, self.sucesor, False)

    def busquedaID(self, conexion, requestData):
        identificador = requestData[1]
        socketData = []
        if (
            self.id != identificador
            and self.sucesorID != self.id
            and self.id <= identificador
            and self.id > self.sucesorID
        ):
            socketData = [0, self.sucesor]

        elif (
            self.id != identificador
            and self.sucesorID != self.id
            and self.id <= identificador
        ):
            value = ()
            for key, value in self.fingerTable.items():
                if key >= identificador:
                    break
            value = self.sucesor
            socketData = [1, value]
        # Caso base: Si el identificador es el mismo que el mío
        elif self.id == identificador or self.sucesorID == self.id:
            socketData = [0, self.direccion]
        # Si el predecesor es mayor que el identificador, entonces soy el nodo
        elif self.predecesorID < identificador or self.predecesorID > self.id:
            socketData = [0, self.direccion]
        # Se manda el precedesor de vuelta
        else:
            socketData = [1, self.predecesor]
        conexion.sendall(pickle.dumps(socketData))

    def actualizarSucesor(self, requestData):
        newSucc = requestData[2]
        self.sucesor = newSucc
        self.sucesorID = self.hashFichero(newSucc[0] + ":" + str(newSucc[1]))

    def actualizarPredecesor(self, requestData):
        newPred = requestData[2]
        self.predecesor = newPred
        self.predecesorID = self.hashFichero(newPred[0] + ":" + str(newPred[1]))

    def start(self):
        # Se aceptan conexiones de otros hilos
        threading.Thread(target=self.listenThread, args=()).start()
        threading.Thread(target=self.pingSucesor, args=()).start()

    def pingSucesor(self):
        while True:
            time.sleep(2)
            # Si sólo hay un nodo no se hace ping
            if self.direccion == self.sucesor:
                continue
            try:
                socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketPeer.connect(self.sucesor)
                socketPeer.sendall(pickle.dumps([2]))  # Send ping request
            except Exception:
                print("\n¡Un nodo se ha desconectado!\nEstabilizando conexión...")
                # Busca el siguiente sucesor en la finger table
                value = ()
                newSuccFound = next(
                    (
                        True
                        for key, value in self.fingerTable.items()
                        if value[0] != self.sucesorID
                    ),
                    False,
                )

                if newSuccFound:
                    # Actualiza el sucesor al nuevo sucesor
                    self.sucesor = value[1]
                    self.sucesorID = self.hashFichero(
                        self.sucesor[0] + ":" + str(self.sucesor[1])
                    )

                    # Le digo al nuevo sucesor que actualice su predecesor a mí
                    socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    socketPeer.connect(self.sucesor)
                    socketPeer.sendall(pickle.dumps([4, 0, self.direccion]))
                    socketPeer.close()
                # Soy el único nodo
                else:
                    self.predecesor = (
                        self.direccion
                    )  # Actualiza el predecesor a mi mismo
                    self.predecesorID = self.id
                    self.sucesor = self.direccion  # Sucesor a este nodo
                    self.sucesorID = self.id
                self.actualizarFingerTable()
                self.updateOtherFTables()

    def unirseRed(self, ip, port):
        try:
            recvIPPort = self.sucesorDHT((ip, port), self.id)
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peerSocket.connect(recvIPPort)
            socketData = [0, self.direccion]

            # Manda la direccion del nodo que se unirá a la red
            peerSocket.sendall(pickle.dumps(socketData))
            # Recibe al nuevo predecesor
            requestData = pickle.loads(peerSocket.recv(self.buffer))
            # Actualiza el precesor y el sucesor
            self.predecesor = requestData[0]
            self.predecesorID = self.hashFichero(
                self.predecesor[0] + ":" + str(self.predecesor[1])
            )
            self.sucesor = recvIPPort
            self.sucesorID = self.hashFichero(recvIPPort[0] + ":" + str(recvIPPort[1]))
            # Le dice al predecesor que actualice su sucesor a mí
            socketData = [4, 1, self.direccion]
            socketPeer2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketPeer2.connect(self.predecesor)
            socketPeer2.sendall(pickle.dumps(socketData))
            socketPeer2.close()
            peerSocket.close()
        except socket.error:
            print("Error en el socket. Comprueba la IP o el puerto.")

    def abandonarRed(self):
        # Le digo a mi sucesor que actualice su predecesor
        socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketPeer.connect(self.sucesor)
        socketPeer.sendall(pickle.dumps([4, 0, self.predecesor]))
        socketPeer.close()

        # Le digo a mi predecesor que actualice su sucesor
        socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socketPeer.connect(self.predecesor)
        socketPeer.sendall(pickle.dumps([4, 1, self.sucesor]))
        socketPeer.close()

        print("Mis ficheros:", self.listaNombresFicheros)
        print("Replicando ficheros al resto de nodos de la red antes de abandonarla...")
        for filename in self.listaNombresFicheros:
            socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socketPeer.connect(self.sucesor)
            socketData = [1, 1, filename]
            socketPeer.sendall(pickle.dumps(socketData))
            with open(filename, "rb") as file:
                # Se consigue la confirmación de que el fichero se ha replicado
                socketPeer.recv(self.buffer)
                self.enviarFichero(socketPeer, filename)
                socketPeer.close()
                print("Fichero (", filename, ") replicado.")
            socketPeer.close()

        # Le digo a los demás nodos que actualicen su fingerTable
        self.updateOtherFTables()

        # Se resetean las variables a por defecto
        self.predecesor = self.direccion
        self.sucesor = self.direccion
        self.predecesorID = self.id
        self.sucesorID = self.id
        self.fingerTable.clear()
        print(self.direccion, "ha abandonado la red.")

    def subirFichero(self, filename, contenido, recvIPport, replicate):
        print("Subiendo el fichero", filename)
        # Si no se encuentra se manda una petición de búsqueda para hacer que un vecino suba el fichero
        socketData = [1]
        if replicate:
            socketData.append(1)
        else:
            socketData.append(-1)
        try:
            self.mandarFichero(filename, contenido, socketData, recvIPport)

        except IOError:
            print("El fichero no se encuentra en el directorio.")
        except socket.error:
            print("Error al subir el fichero.")

    def mandarFichero(self, filename, contenido, socketData, recvIPport):
        # Antes de hacer nada comprueba si existe el fichero o no
        with open(filename, "w") as file:
            print(contenido)
            file.write(contenido)
        socketData += [filename]
        cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cSocket.connect(recvIPport)
        cSocket.sendall(pickle.dumps(socketData))
        self.enviarFichero(cSocket, filename)
        cSocket.close()
        print("Fichero subido.")

    def descargarFichero(self, filename):
        print("Descargando el fichero ", filename)
        fileID = self.hashFichero(filename)

        # Primero busca el nodo que tiene el fichero
        recvIPport = self.sucesorDHT(self.sucesor, fileID)
        socketData = [1, 0, filename]
        cSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cSocket.connect(recvIPport)
        cSocket.sendall(pickle.dumps(socketData))

        # Recibe confirmación si el fichero se ha encontrado
        fileData = cSocket.recv(self.buffer)
        if fileData == b"NoEncontrado":
            print("El fichero ", filename, " no ha sido encontrado.")
        else:
            print("Recibiendo el fichero ", filename)
            self.receiveFile(cSocket, filename)

    def sucesorDHT(self, direccion, identificador):
        # Valores por defecto
        requestData = [1, direccion]
        recvIPPort = requestData[1]

        while requestData[0] == 1:
            peerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                peerSocket.connect(recvIPPort)
                # Manda una petición de búsqueda continua hasta que se encuentre el nodo requerido
                socketData = [3, identificador]
                peerSocket.sendall(pickle.dumps(socketData))
                # Hace una búsqueda continua hasta que se encuentre el nodo requerido
                requestData = pickle.loads(peerSocket.recv(self.buffer))
                recvIPPort = requestData[1]
                peerSocket.close()
            except socket.error:
                print("Conexión denegada mientras se buscaba el sucesor.")
        return recvIPPort

    def actualizarFingerTable(self):
        """
        Actualiza la finger table.
        """
        for i in range(self.max_bits):
            entradaID = (self.id + (2**i)) % self.max_nodos
            # Si sólo hay un nodo en la red
            if self.sucesor == self.direccion:
                self.fingerTable[entradaID] = (self.id, self.direccion)
                continue

            # Si hay más de un nodo en la red, buscamos el sucesor para cada uno
            recvIPPort = self.sucesorDHT(self.sucesor, entradaID)
            recvId = self.hashFichero(recvIPPort[0] + ":" + str(recvIPPort[1]))
            self.fingerTable[entradaID] = (recvId, recvIPPort)

    def updateOtherFTables(self):
        """
        Actualiza las finger tables de los demás nodos de la red.
        """
        here = self.sucesor
        while here != self.direccion:
            socketPeer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                socketPeer.connect(here)  # Connecting to server
                socketPeer.sendall(pickle.dumps([5]))
                here = pickle.loads(socketPeer.recv(self.buffer))
                socketPeer.close()
                if here == self.sucesor:
                    break
            except socket.error:
                print(
                    "Conexión denegada mientras se actualizaba la tabla de finger table."
                )

    def enviarFichero(self, conexion, filename):
        """
        Envia un fichero al socket.
        """
        print("Enviando el fichero ", filename)
        try:
            # Se lee el tamaño del fichero
            with open(filename, "rb") as file:
                print("Tamaño del fichero:", len(file.read()))
        except Exception:
            print("Fichero no encontrado.")
        try:
            with open(filename, "rb") as file:
                while True:
                    fileData = file.read(self.buffer)
                    time.sleep(0.001)
                    if not fileData:
                        break
                    conexion.sendall(fileData)
                print("Fichero (", filename, ") enviado.")
        except Exception:
            print("Fichero no encontrado en el directorio.")

    def receiveFile(self, conexion, filename):
        """
        Recibe un fichero en partes a través de un socket.
        """

        ficheroExiste = False  # Si el fichero ya existe en el directorio
        with contextlib.suppress(FileNotFoundError):
            with open(filename, "rb") as file:
                data = file.read()
                size = len(data)
                if size == 0:
                    print("Se ha vuelto a pedir el fichero.")
                    ficheroExiste = False
                else:
                    print("El fichero ya existe.")
                    ficheroExiste = True
                return
        if not ficheroExiste:
            totalData = b""
            recvSize = 0
            try:
                with open(filename, "wb") as file:
                    while True:
                        fileData = conexion.recv(self.buffer)
                        recvSize += len(fileData)
                        if not fileData:
                            break
                        totalData += fileData
                    file.write(totalData)
            except ConnectionResetError:
                self.connectionReset(filename)

    def connectionReset(self, filename):
        print(
            "Se ha interrumpido la conexión.\nEsperando al sistema para estabilizarse."
        )
        print("Se volverá a intentar en 10 segundos.")
        time.sleep(5)
        os.remove(filename)
        time.sleep(5)
        self.descargarFichero(filename)

    def mostrarFingerTable(self):
        text = ""
        for key, value in self.fingerTable.items():
            text = (
                text + "identificador:" + str(key) + " - Value: " + str(value) + "<br>"
            )
        return text
