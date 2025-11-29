"""
Script para ejecutar tests con diferentes configuraciones.
"""
import subprocess
import sys


def run_command(cmd, description):
    """Ejecuta un comando y muestra resultado."""
    print(f"\n{'='*70}")
    print(f" {description}")
    print('='*70)
    
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def main():
    """Ejecuta batería de tests."""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║         DistriSearch - Suite de Tests                       ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    tests = [
        ("pytest tests/test_hypercube.py -v", "Tests de Hipercubo (Topología y Ruteo)"),
        ("pytest tests/test_election.py -v", "Tests de Elección de Líder (Bully)"),
        ("pytest tests/test_storage.py -v", "Tests de Almacenamiento (Índice Invertido)"),
        ("pytest tests/test_integration.py -v", "Tests de Integración"),
    ]
    
    results = []
    
    for cmd, desc in tests:
        success = run_command(cmd, desc)
        results.append((desc, success))
    
    # Resumen
    print(f"\n{'='*70}")
    print(" RESUMEN DE TESTS")
    print('='*70)
    
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    for desc, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status} - {desc}")
    
    print(f"\n  Total: {passed}/{total} suites pasaron")
    
    if passed == total:
        print("\n  🎉 ¡Todos los tests pasaron!")
        return 0
    else:
        print(f"\n  ⚠ {total - passed} suite(s) fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(main())
