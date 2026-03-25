"""Agentic configuration detection - NO HARDCODING.

All configuration is detected dynamically by the LLM agent exploring the repository.
The agent determines:
- Python version from pyproject.toml, setup.py, .python-version
- Package manager from lock files
- Install commands by trying them
- Test framework by exploring the repo
- Test commands by running them
"""

from __future__ import annotations

from dataclasses import dataclass, field
from logging import getLogger
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from swe_forge.llm.client import LLMClient, GenerationRequest, Message

logger = getLogger(__name__)


# System prompt for agentic configuration detection
CONFIG_DETECTION_SYSTEM_PROMPT = """You are a repository configuration analyzer.

Your job: Analyze a GitHub repository and determine its configuration.

You have access to:
- `shell`: Execute commands to explore the repository
- `read_file`: Read file contents
- `list_dir`: List directory contents

STEPS:
1. Clone the repository at the specified commit
2. Explore to find configuration files:
   - pyproject.toml, setup.py, setup.cfg, requirements.txt
   - .python-version, runtime.txt
   - package.json, Gemfile, Cargo.toml, go.mod
   
3. Detect:
   - Python version (from requires-python or .python-version)
   - Package manager (poetry, uv, pip, pipenv, conda)
   - Test framework (pytest, unittest, nose, etc.)
   - Build system (setup.py, hatch, flit, etc.)
   
4. TRY installation commands and track which ones succeed:
   - poetry install (exit code 0?)
   - pip install -e . (exit code 0?)
   - pip install -r requirements.txt (exit code 0?)
   
5. TRY test commands and track which work:
   - pytest --collect-only (exit code 0?)
   - python -m pytest (exit code 0?)
   - make test (exit code 0?)

6. Return configuration via `submit_config` tool with:
   - python_version: "3.x"
   - package_manager: "pip|poetry|uv|pipenv|conda"
   - install_commands: list of commands that succeeded (exit 0)
   - test_command: the test command that worked
   - test_framework: "pytest|unittest|nose"

ERROR HANDLING:
- If install fails, read error and retry with alternative
- If no test framework found, use "python -m pytest" as fallback
- Report what actually worked, not what should work

DO NOT HARDCODE: You must actually run commands and verify they work.
"""


@dataclass
class RepositoryConfig:
    """Configuration detected by the agent - NO DEFAULTS."""
    
    # Required - must be detected
    python_version: str = ""
    package_manager: str = ""
    
    # Commands that actually worked (verified)
    install_commands: list[str] = field(default_factory=list)
    pre_test_commands: list[str] = field(default_factory=list)
    test_command: str = ""
    test_framework: str = ""
    
    # Docker image to use (derived from python_version)
    docker_image: str = ""
    
    # Validation status
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if config has all required fields."""
        return bool(
            self.python_version and 
            self.package_manager and 
            self.install_commands and
            self.test_command and
            self.validated
        )


class SubmitConfigArgs(BaseModel):
    """Arguments for submit_config tool."""
    
    python_version: str
    package_manager: str
    install_commands: list[str]
    test_command: str
    test_framework: str
    docker_image: str = ""
    validation_notes: list[str] = []


async def detect_repository_config(
    llm_client: "LLMClient",
    sandbox: "SandboxProtocol",
    repo_url: str,
    commit_sha: str,
    max_turns: int = 50,
) -> RepositoryConfig:
    """Detect repository configuration using an agentic LLM loop.
    
    NO HARDCODING - everything is discovered by the agent trying commands.
    """
    from swe_forge.llm.client import GenerationRequest, Message, ToolDefinition
    
    # Tools available to the agent
    tools = [
        _shell_tool_schema(),
        _read_file_tool_schema(),
        _list_dir_tool_schema(),
        _submit_config_tool_schema(),
    ]
    
    # Initial prompt
    initial_prompt = f"""Analyze this repository and detect its configuration.

Repository: {repo_url}
Commit: {commit_sha}

Clone it, explore configuration files, and determine:
1. Python version (try reading pyproject.toml, .python-version, runtime.txt)
2. Package manager (look for poetry.lock, Pipfile, requirements.txt)
3. Install commands (TRY them and report which succeed with exit code 0)
4. Test command (TRY pytest, python -m pytest, make test)

IMPORTANT: You must actually RUN commands and verify they work.
Report ONLY commands that succeeded (exit code 0).

Submit your findings using the submit_config tool.
"""
    
    messages: list[Message] = [
        Message(role="system", content=CONFIG_DETECTION_SYSTEM_PROMPT),
        Message(role="user", content=initial_prompt),
    ]
    
    config_result: RepositoryConfig | None = None
    turns = 0
    
    while turns < max_turns and config_result is None:
        turns += 1
        
        # Request with tools
        request = GenerationRequest(
            model=llm_client.default_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        
        response = await llm_client.complete(request)
        
        if not response.choices:
            break
            
        choice = response.choices[0]
        messages.append(choice.message)
        
        # Handle tool calls
        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                tool_result = await _handle_tool_call(tool_call, sandbox)
                
                messages.append(Message(
                    role="tool",
                    content=tool_result,
                    tool_call_id=tool_call.id,
                ))
                
                # Check if this is submit_config
                if tool_call.function.name == "submit_config":
                    import json
                    args = json.loads(tool_call.function.arguments)
                    config_result = RepositoryConfig(
                        python_version=args.get("python_version", ""),
                        package_manager=args.get("package_manager", ""),
                        install_commands=args.get("install_commands", []),
                        test_command=args.get("test_command", ""),
                        test_framework=args.get("test_framework", ""),
                        docker_image=args.get("docker_image", f"python:{args.get('python_version', '3.11')}-slim"),
                        validated=True,
                    )
        
        # Check for completion
        if choice.finish_reason == "stop" and not choice.message.tool_calls:
            break
    
    return config_result or RepositoryConfig(validated=False, validation_errors=["Agent did not submit config"])


async def _handle_tool_call(tool_call: Any, sandbox: "SandboxProtocol") -> str:
    """Handle a tool call from the agent."""
    import json
    
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    
    if name == "shell":
        cmd = args.get("command", "")
        timeout = args.get("timeout", 120.0)
        result = await sandbox.run_command(cmd, timeout=timeout)
        return f"Exit code: {result.exit_code}\nStdout: {result.stdout}\nStderr: {result.stderr}"
    
    elif name == "read_file":
        path = args.get("path", "")
        content = await sandbox.read_file(path)
        return content[:10000]  # Limit size
    
    elif name == "list_dir":
        path = args.get("path", ".")
        result = await sandbox.run_command(f"ls -la {path}")
        return result.stdout
    
    elif name == "submit_config":
        return "Configuration submitted successfully."
    
    return f"Unknown tool: {name}"


def _shell_tool_schema() -> ToolDefinition:
    """Shell tool for executing commands."""
    return ToolDefinition.create(
        name="shell",
        description="Execute a shell command and return the result",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "number", "description": "Timeout in seconds", "default": 120},
            },
            "required": ["command"],
        },
    )


def _read_file_tool_schema() -> ToolDefinition:
    """Read file tool."""
    return ToolDefinition.create(
        name="read_file",
        description="Read a file's contents",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    )


def _list_dir_tool_schema() -> ToolDefinition:
    """List directory tool."""
    return ToolDefinition.create(
        name="list_dir",
        description="List directory contents",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
            },
        },
    )


def _submit_config_tool_schema() -> ToolDefinition:
    """Submit configuration tool."""
    return ToolDefinition.create(
        name="submit_config",
        description="Submit the detected repository configuration",
        parameters={
            "type": "object",
            "properties": {
                "python_version": {"type": "string", "description": "Detected Python version"},
                "package_manager": {"type": "string", "description": "Detected package manager"},
                "install_commands": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Commands that successfully installed (exit 0)",
                },
                "test_command": {"type": "string", "description": "Command to run tests"},
                "test_framework": {"type": "string", "description": "Detected test framework"},
                "docker_image": {"type": "string", "description": "Docker image to use"},
                "validation_notes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Notes from validation",
                },
            },
            "required": ["python_version", "package_manager", "install_commands", "test_command", "test_framework"],
        },
    )


class SandboxProtocol(Protocol):
    """Protocol for sandbox implementations."""
    
    async def run_command(self, cmd: str, *, timeout: float | None = None) -> "ExecResultProtocol":
        """Execute a command."""
        ...
    
    async def read_file(self, path: str) -> str:
        """Read a file."""
        ...


class ExecResultProtocol(Protocol):
    """Protocol for command execution results."""
    
    @property
    def exit_code(self) -> int: ...
    
    @property
    def stdout(self) -> str: ...
    
    @property
    def stderr(self) -> str: ...
