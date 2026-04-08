#!/usr/bin/env python3
"""Regenerate tests for existing SWE-Forge datasets using the fixed TestGenerator.

Clones repositories directly via git (no GitHub API) to work around rate limits.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_workspace(workspace_path: Path) -> dict:
    with open(workspace_path) as f:
        return yaml.safe_load(f)


def workspace_to_task(workspace: dict, patch_content: str) -> dict:
    task_id = workspace.get("task_id", "")
    repo_data = workspace.get("repo", {})

    repo_url = repo_data.get("url", "")
    if repo_url.startswith("https://github.com/"):
        repo = repo_url.replace("https://github.com/", "").replace(".git", "")
    elif repo_url.startswith("git@github.com:"):
        repo = repo_url.replace("git@github.com:", "").replace(".git", "")
    else:
        repo = task_id.rsplit("-", 1)[0] if "-" in task_id else task_id

    return {
        "id": task_id,
        "repo": repo,
        "base_commit": repo_data.get("base_commit", ""),
        "merge_commit": repo_data.get("merge_commit", ""),
        "language": workspace.get("language", "unknown"),
        "difficulty_score": workspace.get("difficulty_score", 1),
        "prompt": workspace.get("prompt", ""),
        "patch": patch_content,
        "test_patch": "",
        "fail_to_pass": workspace.get("tests", {}).get("fail_to_pass", []),
        "pass_to_pass": workspace.get("tests", {}).get("pass_to_pass", []),
        "install_config": {
            "install_commands": workspace.get("install", {}).get("commands", []),
        },
    }


async def run_command(cmd: str, timeout: float = 300.0) -> tuple[int, str, str]:
    """Run a shell command."""
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode or 0, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Command timed out"


async def regenerate_tests_for_task(
    task_id: str,
    task_dir: Path,
    llm_client,
    model: str = "moonshotai/kimi-k2.5:nitro",
    max_turns: int = 200,
) -> bool:
    """Regenerate tests for a single task."""
    workspace_path = task_dir / "workspace.yaml"
    patch_path = task_dir / "patch.diff"

    if not workspace_path.exists():
        logger.error(f"[{task_id}] workspace.yaml not found")
        return False

    if not patch_path.exists():
        logger.warning(
            f"[{task_id}] patch.diff not found - skipping (need original PR patch)"
        )
        return False

    workspace = load_workspace(workspace_path)
    with open(patch_path) as f:
        patch_content = f.read()

    task_dict = workspace_to_task(workspace, patch_content)

    if not task_dict["base_commit"]:
        logger.error(f"[{task_id}] No base_commit in workspace.yaml")
        return False

    from swe_forge.swe.models import SweTask
    from swe_forge.swe.test_generator import TestGenerator

    task = SweTask(**task_dict)

    logger.info(f"[{task_id}] Regenerating tests...")
    logger.info(f"[{task_id}] Repo: {task.repo}")
    logger.info(f"[{task_id}] Base commit: {task.base_commit[:8]}...")

    work_dir = Path(f"/tmp/swe_forge_regenerate_{task_id}")
    if work_dir.exists():
        await run_command(f"rm -rf {work_dir}")
    work_dir.mkdir(parents=True, exist_ok=True)

    repo_dir = work_dir / "repo"
    repo_url = f"https://github.com/{task.repo}.git"

    logger.info(f"[{task_id}] Cloning {repo_url}...")
    exit_code, stdout, stderr = await run_command(
        f"git clone --depth 1 {repo_url} {repo_dir}", timeout=600.0
    )

    if exit_code != 0:
        logger.error(f"[{task_id}] Clone failed: {stderr}")
        return False

    logger.info(f"[{task_id}] Fetching base commit...")
    exit_code, stdout, stderr = await run_command(
        f"cd {repo_dir} && git fetch --depth 1 origin {task.base_commit}", timeout=300.0
    )

    if exit_code != 0:
        exit_code, stdout, stderr = await run_command(
            f"cd {repo_dir} && git fetch origin {task.base_commit} --depth 1",
            timeout=300.0,
        )

    if exit_code != 0:
        logger.warning(f"[{task_id}] Could not fetch base commit, trying full clone...")
        await run_command(f"rm -rf {repo_dir}")
        exit_code, stdout, stderr = await run_command(
            f"git clone {repo_url} {repo_dir}", timeout=1200.0
        )
        if exit_code != 0:
            logger.error(f"[{task_id}] Full clone failed: {stderr}")
            return False

    exit_code, stdout, stderr = await run_command(
        f"cd {repo_dir} && git checkout {task.base_commit}", timeout=60.0
    )

    if exit_code != 0:
        logger.error(f"[{task_id}] Checkout failed: {stderr}")
        return False

    logger.info(f"[{task_id}] Repository ready at {repo_dir}")

    class LocalSandbox:
        def __init__(self, repo_dir: Path):
            self.repo_dir = repo_dir

        async def run_command(self, cmd: str, timeout: float | None = None):
            full_cmd = f"cd {self.repo_dir} && {cmd}"
            exit_code, stdout, stderr = await run_command(full_cmd, timeout or 300.0)

            class ExecResult:
                @property
                def exit_code(self):
                    return exit_code

                @property
                def stdout(self):
                    return stdout

                @property
                def stderr(self):
                    return stderr

            return ExecResult()

        async def write_file(self, path: str, content: str):
            full_path = self.repo_dir / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        async def read_file(self, path: str):
            full_path = self.repo_dir / path
            with open(full_path) as f:
                return f.read()

        async def setup_workspace(self, repo_url: str, base_commit: str):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    sandbox = LocalSandbox(repo_dir)

    generator = TestGenerator(
        llm=llm_client,
        model=model,
        max_turns=max_turns,
    )

    result = await generator.generate_tests(task, sandbox)

    if not result.success:
        logger.error(
            f"[{task_id}] Test generation failed after {result.turn_count} turns"
        )
        await run_command(f"rm -rf {work_dir}")
        return False

    logger.info(f"[{task_id}] Generated {len(result.fail_to_pass)} fail_to_pass tests")
    logger.info(f"[{task_id}] Generated {len(result.pass_to_pass)} pass_to_pass tests")

    workspace["tests"]["fail_to_pass"] = result.fail_to_pass
    workspace["tests"]["pass_to_pass"] = result.pass_to_pass

    if result.test_files:
        test_patch = "\n".join(
            f"# Test file: {tf.path}\n{tf.content}" for tf in result.test_files
        )
        test_patch_path = task_dir / "test_patch.diff"
        with open(test_patch_path, "w") as f:
            f.write(test_patch)

        tests_dir = task_dir / "tests"
        tests_dir.mkdir(exist_ok=True)
        for tf in result.test_files:
            test_file = tests_dir / tf.path.replace("tests/", "")
            test_file.parent.mkdir(parents=True, exist_ok=True)
            with open(test_file, "w") as f:
                f.write(tf.content)

        logger.info(f"[{task_id}] Wrote {len(result.test_files)} test files")

    if result.install_commands:
        workspace["install"]["commands"] = result.install_commands
        logger.info(f"[{task_id}] Updated install commands")

    if result.dataset_prompt:
        workspace["prompt"] = result.dataset_prompt

    with open(workspace_path, "w") as f:
        yaml.dump(
            workspace, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    logger.info(f"[{task_id}] Successfully regenerated tests")

    await run_command(f"rm -rf {work_dir}")
    return True


async def regenerate_all_datasets(
    datasets_dir: Path,
    limit: int | None = None,
    model: str = "moonshotai/kimi-k2.5:nitro",
    skip_missing_patch: bool = True,
) -> dict[str, bool]:
    from swe_forge.llm.openrouter import OpenRouterClient

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        logger.error("OPENROUTER_API_KEY environment variable not set")
        return {}

    llm_client = OpenRouterClient(api_key=openrouter_key, default_model=model)

    all_dirs = sorted([d for d in datasets_dir.iterdir() if d.is_dir()])

    dataset_dirs = []
    skipped_no_patch = []
    for d in all_dirs:
        patch_path = d / "patch.diff"
        if patch_path.exists():
            dataset_dirs.append(d)
        elif not skip_missing_patch:
            dataset_dirs.append(d)
        else:
            skipped_no_patch.append(d.name)

    if skipped_no_patch:
        logger.info(
            f"Skipping {len(skipped_no_patch)} datasets without patch.diff: {skipped_no_patch}"
        )

    if limit:
        dataset_dirs = dataset_dirs[:limit]

    results = {}

    for dataset_dir in dataset_dirs:
        task_id = dataset_dir.name
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing: {task_id}")
        logger.info(f"{'=' * 60}")

        success = await regenerate_tests_for_task(
            task_id, dataset_dir, llm_client, model
        )
        results[task_id] = success

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate tests for SWE-Forge datasets"
    )
    parser.add_argument("--datasets-dir", type=str, default="./datasets")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model", type=str, default="moonshotai/kimi-k2.5:nitro")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    datasets_dir = Path(args.datasets_dir)
    if not datasets_dir.exists():
        logger.error(f"Datasets directory not found: {datasets_dir}")
        sys.exit(1)

    results = asyncio.run(
        regenerate_all_datasets(
            datasets_dir,
            limit=args.limit,
            model=args.model,
        )
    )

    print("\n" + "=" * 60)
    print("REGENERATION SUMMARY")
    print("=" * 60)
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Total datasets: {total}")
    print(f"Successful: {successful}")
    print(f"Failed: {total - successful}")
    print(f"Success rate: {successful / total * 100:.1f}%" if total > 0 else "N/A")
    print("=" * 60)

    if total - successful > 0:
        print("\n--- FAILED TASKS ---")
        for task_id, success in results.items():
            if not success:
                print(f"  {task_id}")

    sys.exit(0 if successful == total else 1)


if __name__ == "__main__":
    main()
