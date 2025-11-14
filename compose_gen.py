"""
Genera docker-compose.yml dinámicamente basado en HYPERCUBE_SIZE
"""
import yaml
from src.config import HYPERCUBE_SIZE, INIT_PORT

NODES = 2 ** HYPERCUBE_SIZE


def generate_compose():
    compose = {
        'version': '3.8',
        'services': {},
        'networks': {
            'hypfs-network': {
                'driver': 'bridge'
            }
        },
        'volumes': {}
    }

    # Generar servicios IPFS
    for i in range(NODES):
        ipfs_service = {
            'image': 'ipfs/go-ipfs:latest',
            'container_name': f'ipfs-node-{i}',
            'environment': {
                'IPFS_PROFILE': 'server'
            },
            'volumes': [
                f'./data/ipfs{i}:/data/ipfs'
            ],
            'networks': ['hypfs-network'],
            'healthcheck': {
                'test': ['CMD', 'ipfs', 'id'],
                'interval': '10s',
                'timeout': '5s',
                'retries': 5
            }
        }
        compose['services'][f'ipfs-node-{i}'] = ipfs_service

    # Generar servicios HYPFS
    for i in range(NODES):
        binary_id = bin(i)[2:].zfill(HYPERCUBE_SIZE)
        hypfs_service = {
            'build': '.',
            'container_name': f'hypfs-node-{i}',
            'depends_on': {
                f'ipfs-node-{i}': {
                    'condition': 'service_healthy'
                }
            },
            'environment': {
                'IPFS_API_URL': f'http://ipfs-node-{i}:5001',
                'NODE_ID': str(i),
                'NODE_PORT': str(INIT_PORT + i),
                'HYPERCUBE_ID': binary_id
            },
            'volumes': [
                './objects:/app/objects',
                './results:/app/results',
                './test_files:/app/test_files'
            ],
            'networks': ['hypfs-network'],
            'command': ['python', 'server.py', str(INIT_PORT + i)],
            'ports': [f'{INIT_PORT + i}:{INIT_PORT + i}']
        }
        compose['services'][f'hypfs-node-{i}'] = hypfs_service

    # Servicio hops counter
    compose['services']['hops-counter'] = {
        'build': '.',
        'container_name': 'hops-counter',
        'command': ['python', 'hops_counter.py'],
        'networks': ['hypfs-network'],
        'ports': ['5000:5000']  # HOP_SERVER_PORT por defecto
    }

    # Servicio controller/orchestrator
    compose['services']['controller'] = {
        'build': '.',
        'container_name': 'hypfs-controller',
        'depends_on': [f'hypfs-node-{i}' for i in range(NODES)] + ['hops-counter'],
        'environment': {
            'IPFS_API_URL': 'http://ipfs-node-0:5001'
        },
        'volumes': [
            './objects:/app/objects',
            './results:/app/results',
            './test_files:/app/test_files'
        ],
        'networks': ['hypfs-network'],
        'stdin_open': True,
        'tty': True,
        'command': ['python', 'menu.py']
    }

    return compose


def main():
    compose = generate_compose()
    
    with open('docker-compose.yml', 'w') as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)
    
    print(f"✓ docker-compose.yml generado para {NODES} nodos (HYPERCUBE_SIZE={HYPERCUBE_SIZE})")
    print(f"  - {NODES} nodos IPFS")
    print(f"  - {NODES} nodos HYPFS")
    print(f"  - 1 contador de hops")
    print(f"  - 1 controlador")


if __name__ == '__main__':
    main()