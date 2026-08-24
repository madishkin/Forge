import subprocess
from pathlib import Path


def run_command(command: list[str], error_message: str):
    result = subprocess.run(
        command,
        text=True,
        capture_output=True
    )

    if result.returncode != 0:
        print(error_message)
        print(result.stderr)
        exit(1)

    return result


project_path = Path('test-app')
dockerfile = project_path / 'Dockerfile'

if not dockerfile.is_file():
    print('Dockerfile not found')
    exit(1)

print('Dockerfile found')
print('Building Dockerfile')

build_result = run_command(
    ['docker', 'build', '-t', 'forge-test', str(project_path)],
    'Error building Docker image'
)

print('Dockerfile built')

run_result = run_command(
    ['docker', 'run', '--name', 'forge-test-container', 'forge-test'],
    'Error running container'
)

print(run_result.stdout)

state_result = run_command(
    [
        'docker',
        'inspect',
        '--format',
        'Status={{.State.Status}}, Running={{.State.Running}}, ExitCode={{.State.ExitCode}}',
        'forge-test-container'
    ],
    'Error getting container state'
)

print(state_result.stdout)