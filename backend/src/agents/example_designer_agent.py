"""
Example Frontend Design Agent - A local MCP server for UI/UX tasks.

This agent specializes in:
- Generating React components
- Translating UI requirements into TailwindCSS
- Suggesting design improvements

Run this agent locally:
    python -m src.agents.example_designer_agent

Then register it with the platform via the API.
"""

import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="Frontend Design Agent")


@mcp.tool()
def generate_code(
    task_description: str,
    framework: str = "react",
    styling: str = "tailwindcss",
) -> str:
    """
    Generate frontend code based on a task description.

    Args:
        task_description: Description of the UI component or feature
        framework: Framework to use (react, vue, svelte)
        styling: Styling approach (tailwindcss, css-modules, styled-components)

    Returns:
        Generated frontend code
    """
    return f'''"""
Generated {framework.title()} component for: {task_description}
Styling: {styling}
"""

import React from 'react';

interface Props {{
  // TODO: Define props based on requirements
}}

export const GeneratedComponent: React.FC<Props> = () => {{
  return (
    <div className="p-4 bg-white rounded-lg shadow-md">
      <h2 className="text-lg font-semibold text-gray-800">
        {{/* Component content */}}
      </h2>
    </div>
  );
}};

export default GeneratedComponent;
'''


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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote {len(content)} characters to {file_path}"
    except Exception as e:
        return f"Error writing file: {e}"


@mcp.tool()
def suggest_improvements(
    component_code: str,
    focus: str = "accessibility",
) -> str:
    """
    Suggest improvements for a UI component.

    Args:
        component_code: The component code to analyze
        focus: Focus area (accessibility, performance, ux, all)

    Returns:
        Improvement suggestions
    """
    suggestions = []

    if focus in ("accessibility", "all"):
        if "aria-" not in component_code.lower():
            suggestions.append("Consider adding ARIA attributes for better accessibility.")
        if "alt=" not in component_code.lower() and "<img" in component_code.lower():
            suggestions.append("Images should have alt attributes.")
        if "tabindex" not in component_code.lower():
            suggestions.append(
                "Consider tabindex for interactive elements that aren't buttons/links."
            )

    if focus in ("performance", "all"):
        if "useMemo" not in component_code and "map(" in component_code:
            suggestions.append("Consider useMemo for expensive computations in render.")
        if "useCallback" not in component_code and "onClick" in component_code:
            suggestions.append(
                "Consider useCallback for event handlers passed to child components."
            )

    if focus in ("ux", "all"):
        if "loading" not in component_code.lower():
            suggestions.append("Consider adding loading states for async operations.")
        if "error" not in component_code.lower():
            suggestions.append("Consider adding error handling UI.")

    if not suggestions:
        return f"No specific {focus} improvements suggested. Component looks good!"

    return f"Improvement Suggestions ({focus}):\n\n" + "\n\n".join(f"💡 {s}" for s in suggestions)


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
def analyze_component_structure(code: str) -> str:
    """
    Analyze the structure of a React component.

    Args:
        code: The component code to analyze

    Returns:
        Structural analysis report
    """
    findings = []

    component_names = re.findall(r"(?:function|const)\s+(\w+)\s*[=\(]", code)
    if component_names:
        findings.append(f"Components found: {', '.join(component_names)}")

    hooks = re.findall(r"use\w+", code)
    if hooks:
        findings.append(f"React hooks used: {', '.join(set(hooks))}")

    props_match = re.findall(r"interface\s+Props\s*\{([^}]+)\}", code, re.DOTALL)
    if props_match:
        props = [
            p.strip()
            for p in props_match[0].split("\n")
            if p.strip() and not p.strip().startswith("//")
        ]
        findings.append(f"Props defined: {len(props)}")
    else:
        findings.append("No TypeScript props interface found")

    imports = re.findall(r"import.*from\s+['\"]([^'\"]+)['\"]", code)
    if imports:
        findings.append(f"Imports: {len(imports)} modules")

    if "className=" in code:
        findings.append("Uses className (likely TailwindCSS or CSS)")

    if "styled" in code:
        findings.append("Uses styled-components")

    return "Component Analysis:\n\n" + "\n".join(f"- {f}" for f in findings)


if __name__ == "__main__":
    print("Starting Frontend Design Agent MCP Server...")
    print("The platform will connect to this agent at http://localhost:8003/mcp")
    mcp.run(transport="streamable-http")
