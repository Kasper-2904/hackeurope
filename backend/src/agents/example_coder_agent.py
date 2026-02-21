"""
Example Coder Agent - A local MCP server that can be registered with the platform.

This demonstrates how a developer would create a local agent that:
1. Runs an MCP server exposing tools and resources
2. Registers with the platform using the provided token
3. Receives and executes tasks delegated by the orchestrator

Run this agent locally:
    python -m src.agents.example_coder_agent

Then register it with the platform via the API.
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Create the MCP server for this agent
mcp = FastMCP(name="Coder Agent")


# ============== Tools ==============


@mcp.tool()
def read_file(file_path: str) -> str:
    """
    Read the contents of a file.

    Args:
        file_path: Path to the file to read

    Returns:
        The file contents as a string
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    if not path.is_file():
        return f"Error: Not a file: {file_path}"

    try:
        return path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        file_path: Path to the file to write
        content: Content to write to the file

    Returns:
        Success or error message
    """
    path = Path(file_path)

    try:
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


@mcp.tool()
def list_directory(directory_path: str = ".") -> str:
    """
    List contents of a directory.

    Args:
        directory_path: Path to the directory (defaults to current directory)

    Returns:
        List of files and directories
    """
    path = Path(directory_path)
    if not path.exists():
        return f"Error: Directory not found: {directory_path}"

    if not path.is_dir():
        return f"Error: Not a directory: {directory_path}"

    try:
        entries = []
        for entry in sorted(path.iterdir()):
            prefix = "📁 " if entry.is_dir() else "📄 "
            entries.append(f"{prefix}{entry.name}")
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


@mcp.tool()
def search_code(directory: str, pattern: str, file_extension: str = ".py") -> str:
    """
    Search for a pattern in code files.

    Args:
        directory: Directory to search in
        pattern: Text pattern to search for
        file_extension: File extension to filter (default: .py)

    Returns:
        Matching lines with file paths and line numbers
    """
    import re

    path = Path(directory)
    if not path.exists():
        return f"Error: Directory not found: {directory}"

    matches = []
    try:
        for file_path in path.rglob(f"*{file_extension}"):
            try:
                content = file_path.read_text()
                for i, line in enumerate(content.splitlines(), 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        matches.append(f"{file_path}:{i}: {line.strip()}")
            except Exception:
                continue

        if not matches:
            return f"No matches found for '{pattern}'"

        return "\n".join(matches[:50])  # Limit to 50 results
    except Exception as e:
        return f"Error searching: {e}"


@mcp.tool()
def generate_code(
    task_description: str,
    language: str = "python",
    style: str = "clean and well-documented",
) -> str:
    """
    Generate code based on a task description.

    Note: This is a placeholder. In a real implementation, this would
    use an LLM to generate the code.

    Args:
        task_description: Description of what the code should do
        language: Programming language to use
        style: Code style preferences

    Returns:
        Generated code
    """
    # Placeholder - in real implementation, this would call an LLM
    return f'''"""
Generated code for: {task_description}
Language: {language}
Style: {style}

TODO: Implement LLM-based code generation
"""

def placeholder():
    """This is a placeholder function."""
    # Implement the actual logic here
    pass
'''


@mcp.tool()
def run_command(command: str, working_directory: str = ".") -> str:
    """
    Run a shell command and return the output.

    Args:
        command: The command to run
        working_directory: Directory to run the command in

    Returns:
        Command output (stdout and stderr)
    """
    import subprocess

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=working_directory,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]: {result.stderr}"
        if result.returncode != 0:
            output += f"\n[exit code]: {result.returncode}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error running command: {e}"


# ============== Resources ==============


@mcp.resource("workspace://info")
def get_workspace_info() -> str:
    """Get information about the current workspace."""
    cwd = Path.cwd()
    return f"""Workspace Information:
- Current Directory: {cwd}
- Python Version: {os.sys.version}
- Platform: {os.sys.platform}
"""


@mcp.resource("workspace://files")
def get_workspace_files() -> str:
    """Get a list of files in the workspace."""
    cwd = Path.cwd()
    files = []
    for f in cwd.rglob("*"):
        if f.is_file() and ".git" not in str(f):
            files.append(str(f.relative_to(cwd)))
    return "\n".join(sorted(files)[:100])  # Limit to 100 files


# ============== Main ==============


if __name__ == "__main__":
    # Run the MCP server
    # Use streamable-http transport so the platform can connect to it
    print("Starting Coder Agent MCP Server...")
    print("The platform will connect to this agent at http://localhost:8001/mcp")
    mcp.run(transport="streamable-http")
