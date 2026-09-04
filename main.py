import subprocess
import sys
import uuid, json
from pathlib import Path


def run_command(command: list[str], error_message: str):
    result = subprocess.run(
        command,
        text=True,
        capture_output=True
    )

    if result.returncode != 0:
        print(error_message)
        if result.stderr:
            print(result.stderr.strip())
        sys.exit(1)

    return result


def build_image(path: Path, tag: str):
    print('building docker image')
    return run_command(
        ['docker', 'build', '-t', tag, str(path)],
        'error building docker image'
    )


def run_container(image_tag: str, container_name: str):
    print('running container')
    return run_command(
        ['docker', 'run', '-d', '--name', container_name, image_tag],
        'error running container'
    )

def container_logs(container_name: str):
    return run_command(
        ['docker', 'logs', container_name],
        'error getting container logs'
    )

def inspect_container(container_name: str):
    result = run_command(
        ['docker', 'inspect', container_name],
        'error getting container state'
    )
    
    data = json.loads(result.stdout)
    state = data[0]['State']
    
    return {
        'status': state['Status'],
        'running': state['Running'],
        'exit_code': state['ExitCode']
    }           


def main():
    if len(sys.argv) < 2:
        print('usage: python main.py <project_path>')
        sys.exit(1)

    project_path = Path(sys.argv[1])
    dockerfile = project_path / 'Dockerfile'
        
    print(dockerfile)
    if not dockerfile.is_file():
        print('dockerfile not found')
        sys.exit(1)

    print('dockerfile found')

    tag = uuid.uuid4().hex[:7]
    image_tag = f'{project_path.name}:{tag}'
    container_name = f'{project_path.name}-{tag}'

    build_image(project_path, image_tag)
    print('docker image built')

    run_container(image_tag, container_name)

    state_result = inspect_container(container_name)
    if state_result['running']:
        print(f"Deployment success! Container '{container_name}' is running.")
    else:
        log_result = container_logs(container_name)
        logs = (log_result.stdout + log_result.stderr).strip()

        print(f"\nDeployment failed with exit code: {state_result['exit_code']}")
        print("--- Container Logs ---")
        print(logs if logs else "<no logs>")
        print("----------------------")
        sys.exit(1)
    
if __name__ == '__main__':
    main()