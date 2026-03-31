#!/usr/bin/env python3
"""Test SWE-Forge tasks with terminus_2 agent via OpenRouter."""

import argparse
import json
import logging
import subprocess
import os
import re
from typing import Any, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "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")
MODEL = "openai/gpt-5.4"
API_BASE = "https://openrouter.ai/api/v1"


def load_hf_dataset():
    from datasets import load_dataset
    logger.info("Loading dataset from HuggingFace...")
    ds = load_dataset("CortexLM/swe-forge", split="train")
    logger.info(f"Loaded {len(ds)} tasks")
    return ds


def get_task_by_id(ds, task_id: str) -> Dict:
    for row in ds:
        if row["instance_id"] == task_id:
            return dict(row)
    raise ValueError(f"Task not found: {task_id}")


def start_docker_container(task: Dict, timeout: int = 600) -> str:
    task_id = task["instance_id"]
    docker_image = task.get("docker_image", f"platformnetwork/swe-forge:{task_id}")
    container_name = f"swe-agent-{task_id.replace('/', '-').replace('.', '-')}"
    
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
    
    check = subprocess.run(["docker", "images", "-q", docker_image], capture_output=True, text=True)
    if not check.stdout.strip():
        logger.info(f"Pulling: {docker_image}")
        subprocess.run(["docker", "pull", docker_image], capture_output=True, text=True, timeout=300)
    
    logger.info(f"Starting: {container_name}")
    subprocess.run(["docker", "run", "-d", "--name", container_name, docker_image, "sleep", str(timeout + 60)],
                   capture_output=True, text=True, check=True)
    
    # Copy tests from /workspace/tests/ to correct location in /repo
    # Handle nested paths like tests_unit_test_file.py -> tests/unit/test_file.py
    result = subprocess.run(
        ["docker", "exec", container_name, "bash", "-c", """
set -e
cd /repo

# List workspace tests
echo "Copying tests from /workspace/tests/..."

# Handle test files with naming pattern: tests_X_Y_test_file.py -> tests/X/Y/test_file.py
for f in /workspace/tests/*.py; do
    if [ -f "$f" ]; then
        basename=$(basename "$f")
        # Remove .py extension
        name="${basename%.py}"
        
        # Detect pattern: tests_dir_subdir_test_file
        if [[ "$name" =~ ^tests_(.*)_test_(.*)$ ]]; then
            dir_part="${BASH_REMATCH[1]}"
            file_part="test_${BASH_REMATCH[2]}"
            # Replace underscores with slashes for nested dirs
            target_dir="tests/${dir_part//_//}"
            target_file="$target_dir/${file_part}.py"
        elif [[ "$name" =~ ^tests_test_(.*)$ ]]; then
            # Pattern: tests_test_file.py -> tests/test_file.py
            file_part="${BASH_REMATCH[1]}"
            target_dir="tests"
            target_file="$target_dir/test_${file_part}.py"
        else
            # Unknown pattern, just copy to tests/
            target_dir="tests"
            target_file="tests/$basename"
        fi
        
        mkdir -p "$target_dir"
        cp "$f" "$target_file"
        echo "Copied: $basename -> $target_file"
    fi
done

ls -la tests/ 2>/dev/null || true
ls -la tests/unit/ 2>/dev/null || true
"""],
        capture_output=True, text=True
    )
    logger.info(f"Test copy output:\n{result.stdout}")
    if result.returncode != 0:
        logger.warning(f"Test copy stderr: {result.stderr}")
    
    return container_name


def run_agent(task: Dict, container_name: str, max_turns: int = 50) -> Dict[str, Any]:
    from openai import OpenAI
    client = OpenAI(base_url=API_BASE, api_key=OPENROUTER_API_KEY)
    
    task_id = task["instance_id"]
    prompt = task.get("prompt", "")
    
    # Get current state
    result = subprocess.run(["docker", "exec", container_name, "bash", "-c",
                             "cd /repo && head -100 README.md 2>/dev/null || echo 'No README'"], 
                           capture_output=True, text=True)
    readme = result.stdout[:500]
    
    system_prompt = f"""You are solving: "{prompt}"

TASK ID: {task_id}

REPO INFO:
{readme}

INSTRUCTIONS:
1. Apply the gold patch: cd /repo && git apply /workspace/patch.diff
2. If needed, fix any issues
3. Set task_complete: true when done

Respond with JSON: {{"thoughts": "...", "commands": [...], "task_complete": true/false}}
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Apply the patch and verify it works. Use: cd /repo && git apply /workspace/patch.diff"}
    ]
    
    results = {"turns": [], "final_patch": None, "error": None}
    
    for turn in range(max_turns):
        logger.info(f"Turn {turn + 1}/{max_turns}")
        
        try:
            response = client.chat.completions.create(model=MODEL, messages=messages, max_tokens=4096, temperature=0.7)
            assistant_message = response.choices[0].message.content
            messages.append({"role": "assistant", "content": assistant_message})
            
            try:
                start = assistant_message.find("{")
                end = assistant_message.rfind("}") + 1
                action = json.loads(assistant_message[start:end]) if start >= 0 else {"thoughts": assistant_message, "commands": [], "task_complete": False}
            except:
                action = {"thoughts": assistant_message, "commands": [], "task_complete": False}
            
            logger.info(f"Thoughts: {action.get('thoughts', '')[:80]}...")
            
            outputs = []
            for cmd in action.get("commands", []):
                cmd = cmd.strip("'\"")
                logger.info(f"Exec: {cmd[:80]}...")
                result = subprocess.run(["docker", "exec", container_name, "bash", "-lc", cmd],
                                         capture_output=True, text=True, timeout=120)
                outputs.append(f"EXIT={result.returncode}\\n{result.stdout[-1000:]}\\n{result.stderr[:500]}")
                logger.info(f"Exit: {result.returncode}")
            
            results["turns"].append({"turn": turn + 1, "action": action, "outputs": outputs})
            
            if action.get("task_complete"):
                logger.info("Agent completed!")
                break
            
            # Run tests for feedback
            ftp = json.loads(task.get("fail_to_pass", "[]"))
            if ftp:
                test_cmd = ftp[0]
                test_result = subprocess.run(["docker", "exec", container_name, "bash", "-lc",
                                              f"cd /repo && pip install pytest -q 2>/dev/null; {test_cmd} 2>&1 | tail -30"],
                                             capture_output=True, text=True, timeout=120)
                
                user_msg = f"Test: {test_cmd}\\nResult (exit={test_result.returncode}):\\n{test_result.stdout}\\n\\n"
                if test_result.returncode == 0:
                    user_msg += "TESTS PASSED! Set task_complete: true"
                else:
                    user_msg += "FAILED. Apply patch: cd /repo && git checkout . && git apply /workspace/patch.diff"
                messages.append({"role": "user", "content": user_msg})
            else:
                messages.append({"role": "user", "content": "No tests specified. Apply patch and set task_complete: true"})
            
        except Exception as e:
            logger.error(f"Error: {e}")
            results["error"] = str(e)
            break
    
    result = subprocess.run(["docker", "exec", container_name, "bash", "-lc", "cd /repo && git diff"],
                            capture_output=True, text=True)
    results["final_patch"] = result.stdout
    return results


def verify_solution(task: Dict, container_name: str) -> Dict[str, Any]:
    fail_to_pass = json.loads(task.get("fail_to_pass", "[]"))
    pass_to_pass = json.loads(task.get("pass_to_pass", "[]"))
    
    # Install pytest if needed
    subprocess.run(["docker", "exec", container_name, "bash", "-lc", "pip install pytest parameterized -q 2>/dev/null"],
                   capture_output=True, text=True, timeout=60)
    
    results = {"fail_to_pass_results": [], "pass_to_pass_results": [], "all_passed": False}
    
    for cmd in fail_to_pass:
        logger.info(f"Test: {cmd[:60]}...")
        r = subprocess.run(["docker", "exec", container_name, "bash", "-lc", f"cd /repo && {cmd}"],
                           capture_output=True, text=True, timeout=300)
        results["fail_to_pass_results"].append({"command": cmd, "success": r.returncode == 0, "exit_code": r.returncode, "output": r.stdout[-500:], "error": r.stderr[-300:]})
    
    for cmd in pass_to_pass:
        r = subprocess.run(["docker", "exec", container_name, "bash", "-lc", f"cd /repo && {cmd}"],
                           capture_output=True, text=True, timeout=300)
        results["pass_to_pass_results"].append({"command": cmd, "success": r.returncode == 0})
    
    results["all_passed"] = all(r["success"] for r in results["fail_to_pass_results"]) and all(r["success"] for r in results["pass_to_pass_results"])
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", type=str)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=str)
    parser.add_argument("--gold", action="store_true")
    args = parser.parse_args()
    
    ds = load_hf_dataset()
    task = get_task_by_id(ds, args.task_id)
    
    logger.info(f"Task: {task['instance_id']}")
    logger.info(f"Prompt: {task.get('prompt', '')}")
    
    container_name = start_docker_container(task, args.timeout)
    
    try:
        if args.gold:
            subprocess.run(["docker", "exec", container_name, "bash", "-lc", "cd /repo && git apply /workspace/patch.diff"], capture_output=True)
            agent_results = {"turns": [], "final_patch": "GOLD", "error": None}
        else:
            agent_results = run_agent(task, container_name, args.max_turns)
        
        verification = verify_solution(task, container_name)
        
        print(f"\\n{'='*60}")
        print(f"RESULT: {'PASS ✅' if verification['all_passed'] else 'FAIL ❌'}")
        print(f"Turns: {len(agent_results['turns'])}")
        print(f"Patch size: {len(agent_results['final_patch'] or '')} bytes")
        print(f"{'='*60}")
        
        if not verification['all_passed']:
            for r in verification.get("fail_to_pass_results", []):
                if not r["success"]:
                    print(f"Failed: {r['command'][:50]}")
                    print(f"Output: {r.get('output', '')[:200]}")
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump({"task_id": args.task_id, "success": verification["all_passed"], 
                          "turns": len(agent_results["turns"])} | verification, f, indent=2)
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


if __name__ == "__main__":
    main()
