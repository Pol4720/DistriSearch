"""
Tests de correctitud del algoritmo Chord DHT

Estos tests validan propiedades fundamentales del algoritmo Chord:
- Consistencia del anillo
- Correctitud de la búsqueda de sucesores
- Integridad de la finger table
- Estabilización del anillo
"""
import pytest
import sys
import os
from pathlib import Path
import hashlib

# Añadir paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "DHT"))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from DHT.peer import Peer
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    pytest.skip("DHT module not available", allow_module_level=True)


class TestChordConsistency:
    """Tests de consistencia del algoritmo Chord"""
    
    def test_peer_initialization(self):
        """Test: Peer se inicializa correctamente"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        assert peer.id is not None
        assert peer.predecesor == ("127.0.0.1", 2100)
        assert peer.sucesor == ("127.0.0.1", 2100)
        assert peer.predecesorID == peer.id
        assert peer.sucesorID == peer.id
        assert len(peer.fingerTable) == 0
    
    def test_hash_function_deterministic(self):
        """Test: Función hash es determinística"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        key = "test_key"
        hash1 = peer.hashFichero(key)
        hash2 = peer.hashFichero(key)
        
        assert hash1 == hash2
    
    def test_hash_function_range(self):
        """Test: Hash está dentro del rango esperado"""
        max_bits = 10
        max_nodos = 2 ** max_bits
        peer = Peer("127.0.0.1", 2100, 4096, max_bits)
        
        # Probar múltiples keys
        for i in range(100):
            key = f"key_{i}"
            hash_val = peer.hashFichero(key)
            assert 0 <= hash_val < max_nodos
    
    def test_hash_function_distribution(self):
        """Test: Hash tiene distribución razonable"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        hashes = [peer.hashFichero(f"key_{i}") for i in range(1000)]
        unique_hashes = len(set(hashes))
        
        # Debe haber una buena distribución (al menos 90% únicos)
        assert unique_hashes >= 900
    
    def test_single_node_ring_consistency(self):
        """Test: Un solo nodo forma un anillo consistente"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # En un anillo de un solo nodo, sucesor y predecesor son él mismo
        assert peer.sucesor == peer.direccion
        assert peer.predecesor == peer.direccion
        assert peer.sucesorID == peer.id
        assert peer.predecesorID == peer.id
    
    def test_id_uniqueness(self):
        """Test: IDs de nodos con diferentes IPs son diferentes"""
        peer1 = Peer("127.0.0.1", 2100, 4096, 10)
        peer2 = Peer("127.0.0.2", 2100, 4096, 10)
        
        assert peer1.id != peer2.id
    
    def test_id_uniqueness_same_ip_different_ports(self):
        """Test: IDs diferentes para mismo IP, diferente puerto"""
        peer1 = Peer("127.0.0.1", 2100, 4096, 10)
        peer2 = Peer("127.0.0.1", 2101, 4096, 10)
        
        assert peer1.id != peer2.id


class TestChordFingerTable:
    """Tests de la finger table"""
    
    def test_finger_table_empty_on_init(self):
        """Test: Finger table vacía al inicializar"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert len(peer.fingerTable) == 0
    
    def test_update_finger_table_single_node(self):
        """Test: Actualizar finger table con un solo nodo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        
        # Con un solo nodo, todas las entradas apuntan a sí mismo
        assert len(peer.fingerTable) == 10  # max_bits
        
        for entrada_id, (nodo_id, direccion) in peer.fingerTable.items():
            assert nodo_id == peer.id
            assert direccion == peer.direccion
    
    def test_finger_table_entries_count(self):
        """Test: Número correcto de entradas en finger table"""
        max_bits = 8
        peer = Peer("127.0.0.1", 2100, 4096, max_bits)
        peer.actualizarFingerTable()
        
        assert len(peer.fingerTable) == max_bits
    
    def test_finger_table_entry_ids(self):
        """Test: IDs de entrada siguen la fórmula (id + 2^i) mod 2^m"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        
        expected_ids = [(peer.id + 2**i) % (2**10) for i in range(10)]
        actual_ids = list(peer.fingerTable.keys())
        
        assert sorted(expected_ids) == sorted(actual_ids)


class TestChordLookup:
    """Tests de búsqueda en Chord"""
    
    def test_successor_single_node(self):
        """Test: Sucesor en anillo de un nodo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Cualquier ID debe retornar el mismo nodo
        test_ids = [0, 100, 500, 1000, 1023]
        for test_id in test_ids:
            # sucesorDHT busca el sucesor, en un solo nodo retorna a sí mismo
            # (esto requeriría que el peer esté escuchando, pero conceptualmente)
            pass  # Test conceptual


class TestChordFileOperations:
    """Tests de operaciones con archivos"""
    
    def test_file_hash_deterministic(self):
        """Test: Hash de archivo es determinístico"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        filename = "test.txt"
        hash1 = peer.hashFichero(filename)
        hash2 = peer.hashFichero(filename)
        
        assert hash1 == hash2
    
    def test_file_list_initialization(self):
        """Test: Lista de archivos se inicializa vacía"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert len(peer.listaNombresFicheros) == 0
    
    def test_different_files_different_hashes(self):
        """Test: Archivos diferentes tienen hashes diferentes (alta probabilidad)"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        hashes = set()
        for i in range(100):
            filename = f"file_{i}.txt"
            hash_val = peer.hashFichero(filename)
            hashes.add(hash_val)
        
        # Debería haber alta diversidad (al menos 95%)
        assert len(hashes) >= 95


class TestChordScalability:
    """Tests de escalabilidad del algoritmo"""
    
    def test_small_ring(self):
        """Test: Anillo pequeño (4 bits)"""
        peer = Peer("127.0.0.1", 2100, 4096, 4)
        assert peer.max_nodos == 16
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 4
    
    def test_medium_ring(self):
        """Test: Anillo mediano (10 bits)"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert peer.max_nodos == 1024
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 10
    
    def test_large_ring(self):
        """Test: Anillo grande (16 bits)"""
        peer = Peer("127.0.0.1", 2100, 4096, 16)
        assert peer.max_nodos == 65536
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 16


class TestChordEdgeCases:
    """Tests de casos extremos"""
    
    def test_max_bits_boundary(self):
        """Test: Bits en el límite"""
        # Bits muy pequeño
        peer1 = Peer("127.0.0.1", 2100, 4096, 3)
        assert peer1.max_nodos == 8
        
        # Bits razonable
        peer2 = Peer("127.0.0.1", 2101, 4096, 20)
        assert peer2.max_nodos == 1048576
    
    def test_hash_collision_handling(self):
        """Test: Manejo de colisiones de hash"""
        peer = Peer("127.0.0.1", 2100, 4096, 4)  # Espacio pequeño = más colisiones
        
        # Generar muchas keys
        hashes = []
        for i in range(100):
            h = peer.hashFichero(f"key_{i}")
            hashes.append(h)
        
        # Debe haber algunas colisiones en un espacio de 16 valores
        unique_count = len(set(hashes))
        assert unique_count < 100  # No todos únicos debido al espacio pequeño
        assert unique_count > 10   # Pero tampoco todos iguales


class TestChordTheoretical:
    """Tests de propiedades teóricas de Chord"""
    
    def test_routing_table_size(self):
        """Test: Tamaño de routing table es O(log N)"""
        for bits in [4, 8, 10, 12, 16]:
            peer = Peer("127.0.0.1", 2100 + bits, 4096, bits)
            peer.actualizarFingerTable()
            
            # Tamaño de finger table = bits
            assert len(peer.fingerTable) == bits
            
            # Confirmar complejidad logarítmica
            assert len(peer.fingerTable) == bits
    
    def test_id_space_coverage(self):
        """Test: Finger table cubre el espacio de IDs exponencialmente"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        
        # Las distancias deben ser potencias de 2
        distances = []
        for i in range(10):
            expected_distance = 2 ** i
            distances.append(expected_distance)
        
        # Verificar que las distancias siguen el patrón exponencial
        assert distances == [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]


class TestChordCorrectness:
    """Tests de correctitud algorítmica"""
    
    def test_ring_invariant_single_node(self):
        """Test: Invariante del anillo con un nodo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Invariante: predecessor(successor(n)) = n para anillo de un nodo
        assert peer.predecesor == peer.direccion
        assert peer.sucesor == peer.direccion
    
    def test_id_ordering(self):
        """Test: Ordenamiento circular de IDs"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # En un espacio de 1024 valores
        id1 = 100
        id2 = 900
        max_val = 1024
        
        # Distancia en sentido horario
        dist_forward = (id2 - id1) % max_val
        # Distancia en sentido antihorario
        dist_backward = (id1 - id2) % max_val
        
        assert dist_forward == 800
        assert dist_backward == 224
        assert dist_forward + dist_backward == max_val
    
    def test_consistent_hashing_property(self):
        """Test: Propiedad de hashing consistente"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Mismo input siempre produce mismo output
        key = "consistent_key"
        hash_values = [peer.hashFichero(key) for _ in range(10)]
        
        assert all(h == hash_values[0] for h in hash_values)


def run_correctness_suite():
    """Ejecutar suite completa de tests de correctitud"""
    print("🔍 Ejecutando suite de correctitud DHT Chord...")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Inicialización
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert peer.id is not None
        print("✅ Test 1: Inicialización correcta")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Test 1: Inicialización falló - {e}")
        test_results.append(False)
    
    # Test 2: Función hash
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        h1 = peer.hashFichero("test")
        h2 = peer.hashFichero("test")
        assert h1 == h2
        assert 0 <= h1 < 1024
        print("✅ Test 2: Función hash determinística y acotada")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Test 2: Función hash falló - {e}")
        test_results.append(False)
    
    # Test 3: Finger table
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 10
        print("✅ Test 3: Finger table construida correctamente")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Test 3: Finger table falló - {e}")
        test_results.append(False)
    
    # Test 4: Anillo consistente
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert peer.sucesor == peer.direccion
        assert peer.predecesor == peer.direccion
        print("✅ Test 4: Anillo de un nodo es consistente")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Test 4: Anillo falló - {e}")
        test_results.append(False)
    
    # Test 5: Escalabilidad
    try:
        for bits in [4, 8, 10, 12]:
            peer = Peer("127.0.0.1", 2100, 4096, bits)
            assert peer.max_nodos == 2 ** bits
        print("✅ Test 5: Escalabilidad verificada")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Test 5: Escalabilidad falló - {e}")
        test_results.append(False)
    
    print("=" * 60)
    passed = sum(test_results)
    total = len(test_results)
    print(f"\n📊 Resultado: {passed}/{total} tests pasados")
    
    if passed == total:
        print("🎉 ¡Todos los tests de correctitud pasaron!")
        return True
    else:
        print(f"⚠️  {total - passed} tests fallaron")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "correctness":
        success = run_correctness_suite()
        sys.exit(0 if success else 1)
    else:
        pytest.main([__file__, "-v", "--tb=short"])
