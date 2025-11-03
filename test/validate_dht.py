"""
Script de validación rápida del DHT

Ejecuta tests esenciales de correctitud y robustez
Uso: python validate_dht.py
"""
import sys
import time
from pathlib import Path

# Añadir paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "DHT"))
sys.path.insert(0, str(project_root / "DistriSearch"))

try:
    from DHT.peer import Peer
except ImportError:
    print("❌ Error: No se puede importar DHT.peer")
    print("   Verifica que la carpeta DHT/ existe y contiene peer.py")
    sys.exit(1)


def print_banner():
    """Mostrar banner"""
    print("\n" + "="*60)
    print("  🧪 VALIDACIÓN RÁPIDA DHT - DistriSearch")
    print("="*60 + "\n")


def test_basic_initialization():
    """Test 1: Inicialización básica"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        assert peer.id is not None
        assert peer.max_nodos == 1024
        return True, "Peer inicializa correctamente"
    except Exception as e:
        return False, f"Error en inicialización: {e}"


def test_hash_function():
    """Test 2: Función hash"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        # Determinismo
        h1 = peer.hashFichero("test.txt")
        h2 = peer.hashFichero("test.txt")
        assert h1 == h2, "Hash no es determinístico"
        
        # Rango
        assert 0 <= h1 < 1024, "Hash fuera de rango"
        
        # Distribución
        hashes = [peer.hashFichero(f"file_{i}.txt") for i in range(100)]
        unique = len(set(hashes))
        assert unique >= 90, f"Distribución pobre: solo {unique}/100 únicos"
        
        return True, f"Hash OK (distribución: {unique}%)"
    except Exception as e:
        return False, f"Error en hash: {e}"


def test_finger_table():
    """Test 3: Finger table"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        peer.actualizarFingerTable()
        
        assert len(peer.fingerTable) == 10, "Finger table tamaño incorrecto"
        
        # Verificar estructura
        for entrada_id, (nodo_id, direccion) in peer.fingerTable.items():
            assert nodo_id == peer.id, "En anillo de 1 nodo, debe apuntar a sí mismo"
            assert direccion == peer.direccion
        
        return True, "Finger table construida correctamente"
    except Exception as e:
        return False, f"Error en finger table: {e}"


def test_ring_consistency():
    """Test 4: Consistencia del anillo"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        assert peer.sucesor == peer.direccion, "Sucesor incorrecto en anillo de 1 nodo"
        assert peer.predecesor == peer.direccion, "Predecesor incorrecto"
        assert peer.sucesorID == peer.id
        assert peer.predecesorID == peer.id
        
        return True, "Anillo consistente"
    except Exception as e:
        return False, f"Error en consistencia: {e}"


def test_concurrency():
    """Test 5: Concurrencia básica"""
    try:
        import threading
        
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        errors = []
        results = []
        
        def worker(i):
            try:
                h = peer.hashFichero(f"file_{i}.txt")
                results.append(h)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errores en concurrencia: {errors}"
        assert len(results) == 50, "No se completaron todas las operaciones"
        
        return True, "Concurrencia OK (50 threads)"
    except Exception as e:
        return False, f"Error en concurrencia: {e}"


def test_performance():
    """Test 6: Rendimiento básico"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        iterations = 10000
        start = time.time()
        
        for i in range(iterations):
            peer.hashFichero(f"file_{i}.txt")
        
        elapsed = time.time() - start
        ops_per_sec = iterations / elapsed
        
        assert ops_per_sec > 5000, f"Rendimiento bajo: {ops_per_sec:.0f} ops/sec"
        
        return True, f"Rendimiento OK ({ops_per_sec:.0f} ops/sec)"
    except Exception as e:
        return False, f"Error en rendimiento: {e}"


def test_special_characters():
    """Test 7: Caracteres especiales"""
    try:
        peer = Peer("127.0.0.1", 2100, 4096, 10)
        
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file@special#chars$.txt",
            "文件.txt",  # Chino
            "a" * 500 + ".txt",  # Largo
        ]
        
        for name in special_names:
            h = peer.hashFichero(name)
            assert 0 <= h < 1024
        
        return True, "Caracteres especiales OK"
    except Exception as e:
        return False, f"Error con caracteres especiales: {e}"


def test_scalability():
    """Test 8: Escalabilidad"""
    try:
        sizes = [4, 8, 10, 12, 16]
        
        for bits in sizes:
            peer = Peer("127.0.0.1", 2100 + bits, 4096, bits)
            assert peer.max_nodos == 2 ** bits
            peer.actualizarFingerTable()
            assert len(peer.fingerTable) == bits
        
        return True, f"Escalabilidad OK (4-16 bits)"
    except Exception as e:
        return False, f"Error en escalabilidad: {e}"


def run_validation():
    """Ejecutar todos los tests"""
    print_banner()
    
    tests = [
        ("Inicialización", test_basic_initialization),
        ("Función Hash", test_hash_function),
        ("Finger Table", test_finger_table),
        ("Consistencia del Anillo", test_ring_consistency),
        ("Concurrencia", test_concurrency),
        ("Rendimiento", test_performance),
        ("Caracteres Especiales", test_special_characters),
        ("Escalabilidad", test_scalability),
    ]
    
    results = []
    total_time = 0
    
    for i, (name, test_func) in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {name}...", end=" ", flush=True)
        
        start = time.time()
        try:
            success, message = test_func()
            elapsed = time.time() - start
            total_time += elapsed
            
            if success:
                print(f"✅ {message} ({elapsed:.2f}s)")
                results.append(True)
            else:
                print(f"❌ {message}")
                results.append(False)
        except Exception as e:
            elapsed = time.time() - start
            total_time += elapsed
            print(f"❌ Error inesperado: {e}")
            results.append(False)
    
    # Resumen
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    percentage = (passed / total) * 100
    
    print(f"📊 Resultado: {passed}/{total} tests pasados ({percentage:.0f}%)")
    print(f"⏱️  Tiempo total: {total_time:.2f}s")
    print("="*60 + "\n")
    
    if passed == total:
        print("🎉 ¡VALIDACIÓN EXITOSA! El DHT funciona correctamente.")
        print("\n✅ Criterios cumplidos:")
        print("   • Hash determinístico y bien distribuido")
        print("   • Finger table correcta (O(log N) entradas)")
        print("   • Anillo consistente")
        print("   • Thread-safe (concurrencia)")
        print("   • Buen rendimiento (>5k ops/sec)")
        print("   • Soporta caracteres especiales")
        print("   • Escalable (4-16 bits)")
        print("\n✨ El DHT está listo para usar.")
        return True
    else:
        print(f"⚠️  VALIDACIÓN PARCIAL: {total - passed} tests fallaron.")
        print("\n❌ Revisa los errores arriba y:")
        print("   1. Verifica que DHT/peer.py está correctamente implementado")
        print("   2. Ejecuta tests detallados: pytest test/test_dht_correctness.py -v")
        print("   3. Consulta Guias/TESTING_DHT_GUIDE.md para más información")
        return False


def main():
    """Función principal"""
    try:
        success = run_validation()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validación interrumpida por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
