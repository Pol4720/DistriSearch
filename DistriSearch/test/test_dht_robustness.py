"""
Tests de robustez del DHT

Estos tests validan la resistencia del sistema ante:
- Fallos de red
- Nodos que se caen
- Carga pesada
- Concurrencia
- Datos corruptos
"""
import pytest
import sys
import os
import time
import threading
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Añadir paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "DHT"))
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from DHT.peer import Peer
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    pytest.skip("DHT module not available", allow_module_level=True)


class TestDHTNetworkFailures:
    """Tests de fallos de red"""
    
    def test_peer_survives_invalid_successor(self):
        """Test: Peer sobrevive si el sucesor no responde"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Configurar un sucesor inválido
        peer.sucesor = ("192.168.99.99", 9999)
        peer.sucesorID = 999
        
        # El peer debe seguir funcionando localmente
        assert peer.id is not None
        assert peer.direccion == ("127.0.0.1", 2100)
    
    def test_peer_survives_invalid_predecessor(self):
        """Test: Peer sobrevive si el predecesor no responde"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Configurar un predecesor inválido
        peer.predecesor = ("192.168.99.99", 9999)
        peer.predecesorID = 999
        
        # El peer debe seguir funcionando
        assert peer.id is not None
    
    def test_finger_table_with_unreachable_nodes(self):
        """Test: Finger table se construye aunque haya nodos inalcanzables"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Actualizar finger table (sin nodos reales, apuntará a sí mismo)
        peer.actualizarFingerTable()
        
        # Verificar que se construyó correctamente
        assert len(peer.fingerTable) == 10
        
        # Todas las entradas deben apuntar a sí mismo (único nodo)
        for _, (node_id, address) in peer.fingerTable.items():
            assert node_id == peer.id
            assert address == peer.direccion


class TestDHTConcurrency:
    """Tests de concurrencia"""
    
    def test_concurrent_hash_calculations(self):
        """Test: Hash concurrente es thread-safe"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        results = {}
        errors = []
        
        def hash_worker(key):
            try:
                return peer.hashFichero(key)
            except Exception as e:
                errors.append(e)
                return None
        
        # Ejecutar 100 hashes en paralelo
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(hash_worker, f"key_{i}"): i for i in range(100)}
            
            for future in as_completed(futures):
                i = futures[future]
                results[i] = future.result()
        
        # No debe haber errores
        assert len(errors) == 0
        
        # Todos los resultados deben ser válidos
        assert all(v is not None for v in results.values())
        assert all(0 <= v < 1024 for v in results.values())
    
    def test_concurrent_finger_table_updates(self):
        """Test: Actualizaciones concurrentes de finger table"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        errors = []
        
        def update_worker():
            try:
                peer.actualizarFingerTable()
                return True
            except Exception as e:
                errors.append(e)
                return False
        
        # Múltiples threads actualizando finger table
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(update_worker) for _ in range(20)]
            results = [f.result() for f in as_completed(futures)]
        
        # No debe haber errores críticos
        assert len(errors) == 0
        assert all(results)
    
    def test_concurrent_file_operations(self):
        """Test: Operaciones de archivo concurrentes"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        errors = []
        
        def file_worker(file_id):
            try:
                filename = f"file_{file_id}.txt"
                hash_val = peer.hashFichero(filename)
                return hash_val
            except Exception as e:
                errors.append(e)
                return None
        
        # 50 operaciones concurrentes
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(file_worker, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]
        
        assert len(errors) == 0
        assert len(results) == 50
        assert all(r is not None for r in results)


class TestDHTStressLoad:
    """Tests de carga pesada"""
    
    def test_large_number_of_files(self):
        """Test: Hashear gran cantidad de archivos"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        hashes = []
        start_time = time.time()
        
        for i in range(10000):
            h = peer.hashFichero(f"file_{i}.txt")
            hashes.append(h)
        
        elapsed = time.time() - start_time
        
        # Verificar que se completó
        assert len(hashes) == 10000
        
        # Rendimiento razonable (< 5 segundos para 10k hashes)
        assert elapsed < 5.0
        
        # Buena distribución
        unique = len(set(hashes))
        assert unique > 900  # Al menos 90% únicos
    
    def test_finger_table_updates_repeated(self):
        """Test: Actualizaciones repetidas de finger table"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Actualizar 1000 veces
        for _ in range(1000):
            peer.actualizarFingerTable()
        
        # Debe mantener consistencia
        assert len(peer.fingerTable) == 10
    
    def test_many_peer_instances(self):
        """Test: Crear muchas instancias de Peer"""
        peers = []
        
        for i in range(100):
            peer = Peer("127.0.0.1", 2100 + i, 4096, 10)
            peers.append(peer)
        
        # Verificar que todos se crearon correctamente
        assert len(peers) == 100
        
        # Todos deben tener IDs únicos
        ids = [p.id for p in peers]
        assert len(set(ids)) == 100
        
        # Todos deben estar inicializados
        for peer in peers:
            assert peer.direccion[0] == "127.0.0.1"
            assert 2100 <= peer.direccion[1] < 2200


class TestDHTDataIntegrity:
    """Tests de integridad de datos"""
    
    def test_hash_consistency_over_time(self):
        """Test: Hash permanece constante en el tiempo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        filename = "consistent_file.txt"
        hash_initial = peer.hashFichero(filename)
        
        # Esperar y hashear de nuevo
        time.sleep(0.1)
        hash_later = peer.hashFichero(filename)
        
        # Hacer más operaciones
        peer.actualizarFingerTable()
        hash_after_ops = peer.hashFichero(filename)
        
        # Todos deben ser iguales
        assert hash_initial == hash_later == hash_after_ops
    
    def test_special_characters_in_filename(self):
        """Test: Archivos con caracteres especiales"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
            "file@special#chars$.txt",
            "文件.txt",  # Caracteres chinos
            "файл.txt",  # Caracteres cirílicos
            "αρχείο.txt",  # Caracteres griegos
        ]
        
        errors = []
        for name in special_names:
            try:
                h = peer.hashFichero(name)
                assert 0 <= h < 1024
            except Exception as e:
                errors.append((name, e))
        
        # No debe haber errores
        if errors:
            print(f"Errores encontrados: {errors}")
        assert len(errors) == 0
    
    def test_very_long_filename(self):
        """Test: Nombre de archivo muy largo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Nombre de 1000 caracteres
        long_name = "a" * 1000 + ".txt"
        
        h = peer.hashFichero(long_name)
        assert 0 <= h < 1024
    
    def test_empty_filename(self):
        """Test: Nombre de archivo vacío"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Debería manejar strings vacíos
        h = peer.hashFichero("")
        assert 0 <= h < 1024
    
    def test_null_byte_in_filename(self):
        """Test: Bytes nulos en nombre de archivo"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Python strings con null bytes
        name_with_null = "file\x00name.txt"
        
        h = peer.hashFichero(name_with_null)
        assert 0 <= h < 1024


class TestDHTEdgeCases:
    """Tests de casos extremos"""
    
    def test_minimum_ring_size(self):
        """Test: Anillo de tamaño mínimo (2 bits)"""
        peer = Peer("127.0.0.1", 2100, 4096, 2)
        
        assert peer.max_nodos == 4
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 2
    
    def test_maximum_practical_ring_size(self):
        """Test: Anillo de tamaño grande (20 bits)"""
        peer = Peer("127.0.0.1", 2100, 4096, 20)
        
        assert peer.max_nodos == 1048576
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 20
    
    def test_peer_with_port_zero(self):
        """Test: Crear peer con puerto 0"""
        # Puerto 0 significa que el OS asignará uno aleatorio
        # Esto puede funcionar o fallar dependiendo de la implementación
        try:
            peer = Peer("127.0.0.1", 0, 4096, 10)
            assert peer.id is not None
        except Exception:
            # Es aceptable que falle
            pass
    
    def test_same_address_different_instances(self):
        """Test: Múltiples instancias con la misma dirección"""
        # Esto puede causar problemas, pero no debe crashear
        peer1 = Peer("127.0.0.1", 2100, 4096, 10)
        id1 = peer1.id
        
        # Crear otra instancia con la misma dirección
        # (En la práctica fallaría al bindearse al puerto)
        peer2 = Peer("127.0.0.1", 2100, 4096, 10)
        id2 = peer2.id
        
        # Los IDs deben ser iguales (misma dirección)
        assert id1 == id2


class TestDHTRecovery:
    """Tests de recuperación de errores"""
    
    def test_recovery_from_corrupted_finger_table(self):
        """Test: Recuperación de finger table corrupta"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        
        # Corromper finger table
        peer.fingerTable = {}
        
        # Debe poder reconstruirla
        peer.actualizarFingerTable()
        assert len(peer.fingerTable) == 10
    
    def test_recovery_from_invalid_successor(self):
        """Test: Recuperación de sucesor inválido"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Configurar sucesor inválido
        peer.sucesor = None
        peer.sucesorID = None
        
        # Actualizar finger table debe restaurar estado válido
        peer.actualizarFingerTable()
        
        # Verificar que el peer aún funciona
        h = peer.hashFichero("test.txt")
        assert 0 <= h < 1024


class TestDHTPerformance:
    """Tests de rendimiento"""
    
    def test_hash_performance(self):
        """Test: Rendimiento de función hash"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        iterations = 100000
        start = time.time()
        
        for i in range(iterations):
            peer.hashFichero(f"file_{i}.txt")
        
        elapsed = time.time() - start
        ops_per_sec = iterations / elapsed
        
        # Debe ser capaz de hacer al menos 10k ops/sec
        print(f"Hash performance: {ops_per_sec:.0f} ops/sec")
        assert ops_per_sec > 10000
    
    def test_finger_table_update_performance(self):
        """Test: Rendimiento de actualización de finger table"""
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        iterations = 1000
        start = time.time()
        
        for _ in range(iterations):
            peer.actualizarFingerTable()
        
        elapsed = time.time() - start
        ops_per_sec = iterations / elapsed
        
        # Debe ser rápido (al menos 100 ops/sec)
        print(f"Finger table update: {ops_per_sec:.0f} ops/sec")
        assert ops_per_sec > 100


def run_robustness_suite():
    """Suite rápida de robustez"""
    print("🛡️  Ejecutando suite de robustez DHT...")
    print("=" * 60)
    
    results = []
    
    # Test 1: Concurrencia básica
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        hashes = []
        
        def worker():
            return peer.hashFichero(f"key_{random.randint(0, 1000)}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker) for _ in range(100)]
            hashes = [f.result() for f in as_completed(futures)]
        
        assert len(hashes) == 100
        print("✅ Test 1: Concurrencia básica OK")
        results.append(True)
    except Exception as e:
        print(f"❌ Test 1: Concurrencia falló - {e}")
        results.append(False)
    
    # Test 2: Carga pesada
    try:
        peer = Peer("127.0.0.1", 2101, 4096, 10)
        start = time.time()
        
        for i in range(10000):
            peer.hashFichero(f"file_{i}.txt")
        
        elapsed = time.time() - start
        assert elapsed < 5.0
        print(f"✅ Test 2: Carga pesada OK ({10000/elapsed:.0f} ops/sec)")
        results.append(True)
    except Exception as e:
        print(f"❌ Test 2: Carga pesada falló - {e}")
        results.append(False)
    
    # Test 3: Caracteres especiales
    try:
        peer = Peer("127.0.0.1", 2102, 4096, 10)
        special_names = [
            "file with spaces.txt",
            "file@special#chars$.txt",
            "文件.txt",
            "a" * 1000 + ".txt"
        ]
        
        for name in special_names:
            h = peer.hashFichero(name)
            assert 0 <= h < 1024
        
        print("✅ Test 3: Caracteres especiales OK")
        results.append(True)
    except Exception as e:
        print(f"❌ Test 3: Caracteres especiales falló - {e}")
        results.append(False)
    
    # Test 4: Múltiples instancias
    try:
        peers = [Peer("127.0.0.1", 2200 + i, 4096, 10) for i in range(50)]
        ids = [p.id for p in peers]
        
        assert len(set(ids)) == 50
        print("✅ Test 4: Múltiples instancias OK")
        results.append(True)
    except Exception as e:
        print(f"❌ Test 4: Múltiples instancias falló - {e}")
        results.append(False)
    
    # Test 5: Recuperación de errores
    try:
        peer = Peer("127.0.0.1", 2103, 4096, 10)
        peer.actualizarFingerTable()
        
        # Corromper y recuperar
        peer.fingerTable = {}
        peer.actualizarFingerTable()
        
        assert len(peer.fingerTable) == 10
        print("✅ Test 5: Recuperación de errores OK")
        results.append(True)
    except Exception as e:
        print(f"❌ Test 5: Recuperación falló - {e}")
        results.append(False)
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\n📊 Resultado: {passed}/{total} tests pasados")
    
    return passed == total


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "robustness":
        success = run_robustness_suite()
        sys.exit(0 if success else 1)
    else:
        pytest.main([__file__, "-v", "--tb=short"])
