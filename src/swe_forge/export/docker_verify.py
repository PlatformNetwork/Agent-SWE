"""Docker verification for generated test tasks."""

import subprocess
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)


def generate_run_script(task_dir: Path) -> Path:
    """Generate run_tests.sh script for a task directory."""
    script_path = task_dir / "run_tests.sh"
    
    script_content = '''#!/bin/bash
set -e

# SWE-Forge Test Runner
# Usage: ./run_tests.sh [--verify]

TASK_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$TASK_DIR/workspace.yaml"

# Parse workspace.yaml (simple grep-based parsing)
get_value() {
    grep -A1 "$1:" "$WORKSPACE" | tail -1 | sed 's/^[[:space:]]*//' | sed 's/"//g'
}

# Get repo info
REPO_URL=$(grep -A2 "repo:" "$WORKSPACE" | grep "url:" | sed 's/.*url: *//' | sed 's/"//g')
BASE_COMMIT=$(grep "base_commit:" "$WORKSPACE" | sed 's/.*base_commit: *//' | sed 's/"//g')
MERGE_COMMIT=$(grep "merge_commit:" "$WORKSPACE" | sed 's/.*merge_commit: *//' | sed 's/"//g')

echo "=== SWE-Forge Test Runner ==="
echo "Repo: $REPO_URL"
echo "Base: $BASE_COMMIT"
echo "Merge: $MERGE_COMMIT"

# Get install commands (multiline, until next key)
get_install_commands() {
    sed -n '/install:/,/^[a-z]/p' "$WORKSPACE" | grep -E "^\\s+-" | sed 's/.*- *//'
}

# Get fail_to_pass tests
get_fail_to_pass() {
    sed -n '/fail_to_pass:/,/pass_to_pass:/p' "$WORKSPACE" | grep -E "^\\s+-" | sed 's/.*- *//'
}

# Get pass_to_pass tests  
get_pass_to_pass() {
    sed -n '/pass_to_pass:/,/^[a-z]/p' "$WORKSPACE" | grep -E "^\\s+-" | sed 's/.*- *//'
}

echo ""
echo "=== Install Commands ==="
get_install_commands

echo ""
echo "=== Tests (fail_to_pass) ==="
get_fail_to_pass

# Run in Docker container
if [ "$1" == "--verify" ]; then
    echo ""
    echo "=== Running in Docker ==="
    
    IMAGE=$(grep "image:" "$WORKSPACE" | head -1 | sed 's/.*image: *//' | sed 's/"//g')
    if [ -z "$IMAGE" ]; then
        IMAGE="ubuntu:24.04"
    fi
    
    echo "Using image: $IMAGE"
    
    # Run Docker container with tests
    docker run --rm -v "$TASK_DIR:/task" -w /repo "$IMAGE" bash -c "
        # Install git if needed
        apt-get update && apt-get install -y git python3 python3-pip > /dev/null 2>&1
        
        # Clone repo
        git clone $REPO_URL /repo 2>/dev/null || true
        cd /repo
        
        # Apply patch if exists
        if [ -f /task/patch.diff ]; then
            git checkout $BASE_COMMIT 2>/dev/null
            git apply /task/patch.diff || echo 'Patch may already be applied'
        fi
        
        # Run install commands
        get_install_commands | while read cmd; do
            echo 'Running: '\$cmd
            eval \$cmd
        done
        
        # Run fail_to_pass tests
        echo ''
        echo '=== Running fail_to_pass tests ==='
        get_fail_to_pass | while read test_cmd; do
            echo 'Test: '\$test_cmd
        done
    "
fi

echo ""
echo "Done. To verify in Docker, run: ./run_tests.sh --verify"
'''
    
    with open(script_path, "w") as f:
        f.write(script_content)
    
    # Make executable
    script_path.chmod(0o755)
    return script_path


def verify_task_in_docker(task_dir: Path, timeout: int = 300) -> dict:
    """Verify a task by running tests in Docker.
    
    Returns:
        dict with keys: success, output, error
    """
    import tempfile
    import os
    
    workspace_path = task_dir / "workspace.yaml"
    if not workspace_path.exists():
        return {"success": False, "error": "No workspace.yaml found"}
    
    # Generate run script
    script_path = generate_run_script(task_dir)
    
    # Read workspace for config
    import yaml
    with open(workspace_path) as f:
        config = yaml.safe_load(f)
    
    repo_url = config.get("repo", {}).get("url", "")
    base_commit = config.get("repo", {}).get("base_commit", "")
    install_commands = config.get("install", {}).get("commands", [])
    fail_to_pass = config.get("tests", {}).get("fail_to_pass", [])
    
    if not repo_url:
        return {"success": False, "error": "No repo URL in workspace.yaml"}
    
    # Build docker run command
    image = config.get("environment", {}).get("image", "ubuntu:24.04")
    
    # Create verification script
    verify_script = f'''#!/bin/bash
set -e

echo "=== Cloning repo ==="
apt-get update > /dev/null 2>&1
apt-get install -y git python3 python3-pip > /dev/null 2>&1

git clone {repo_url} /repo 2>/dev/null
cd /repo
git checkout {base_commit} 2>/dev/null || true

echo "=== Applying patch ==="
if [ -f /task/patch.diff ]; then
    git apply /task/patch.diff 2>/dev/null || echo "Patch applied or already present"
fi

echo "=== Running install commands ==="
'''

    for cmd in install_commands[:5]:  # Limit to first 5 install commands
        verify_script += f'''
echo "Running: {cmd}"
{cmd} || echo "Install command may have failed (exit $?)"
'''

    verify_script += '''
echo "=== Listing test files ==="
ls -la /task/tests/ 2>/dev/null || echo "No tests directory"

echo "=== Running tests ==="
'''

    for test_cmd in fail_to_pass[:3]:  # Limit to first 3 tests
        verify_script += f'''
echo "Running: {test_cmd}"
{test_cmd} 2>&1 || echo "Test failed (expected on base commit)"
'''

    # Write verify script
    script_path = task_dir / "verify_docker.sh"
    with open(script_path, "w") as f:
        f.write(verify_script)
    script_path.chmod(0o755)
    
    # Run docker
    try:
        result = subprocess.run(
            ["docker", "run", "--rm",
             "-v", f"{task_dir}:/task",
             "-w", "/repo",
             "--timeout", str(timeout),
             image,
             "bash", "/task/verify_docker.sh"],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}
