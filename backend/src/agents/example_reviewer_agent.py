"""
Example Code Reviewer Agent - A local MCP server for code review tasks.

This agent specializes in reviewing code for:
- Code quality and best practices
- Security vulnerabilities
- Performance issues
- Documentation completeness

Run this agent locally:
    python -m src.agents.example_reviewer_agent

Then register it with the platform via the API.
"""

import ast
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Create the MCP server for this agent
mcp = FastMCP(name="Code Reviewer Agent")


# ============== Tools ==============


@mcp.tool()
def review_code(code: str, language: str = "python") -> str:
    """
    Review code for quality, best practices, and potential issues.

    Args:
        code: The code to review
        language: Programming language (default: python)

    Returns:
        Review findings with suggestions
    """
    findings = []

    if language == "python":
        findings.extend(_check_python_code(code))
    else:
        findings.append(f"Note: Basic review only - {language} specific checks not implemented")

    # General checks
    findings.extend(_check_general_issues(code))

    if not findings:
        return "No issues found. Code looks good!"

    return "Code Review Findings:\n\n" + "\n\n".join(f"- {f}" for f in findings)


def _check_python_code(code: str) -> list[str]:
    """Check Python-specific issues."""
    findings = []

    # Try to parse the code
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntax Error: {e}"]

    # Check for common issues
    for node in ast.walk(tree):
        # Check for bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append("Bare 'except:' clause found. Consider catching specific exceptions.")

        # Check for mutable default arguments
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(
                        f"Function '{node.name}' has mutable default argument. "
                        "Use None and initialize inside the function."
                    )

            # Check for missing docstring
            if not ast.get_docstring(node):
                findings.append(f"Function '{node.name}' is missing a docstring.")

        # Check class docstrings
        if isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node):
                findings.append(f"Class '{node.name}' is missing a docstring.")

    return findings


def _check_general_issues(code: str) -> list[str]:
    """Check for general code issues."""
    findings = []
    lines = code.splitlines()

    for i, line in enumerate(lines, 1):
        # Check line length
        if len(line) > 120:
            findings.append(f"Line {i} exceeds 120 characters ({len(line)} chars)")

        # Check for TODO/FIXME
        if re.search(r"\b(TODO|FIXME|XXX|HACK)\b", line, re.IGNORECASE):
            findings.append(f"Line {i} contains TODO/FIXME marker")

        # Check for hardcoded credentials patterns
        if re.search(
            r"(password|secret|api_key|token)\s*=\s*['\"][^'\"]+['\"]", line, re.IGNORECASE
        ):
            findings.append(
                f"Line {i}: Possible hardcoded credential. Consider using environment variables."
            )

        # Check for print statements (in Python)
        if re.match(r"\s*print\s*\(", line):
            findings.append(f"Line {i}: Consider using logging instead of print statements.")

    return findings


@mcp.tool()
def check_security(code: str) -> str:
    """
    Check code for common security vulnerabilities.

    Args:
        code: The code to check

    Returns:
        Security findings
    """
    findings = []

    # SQL injection patterns
    if re.search(r"(execute|cursor\.execute)\s*\([^)]*%s|f['\"].*SELECT.*\{", code):
        findings.append(
            "SECURITY: Potential SQL injection vulnerability. Use parameterized queries."
        )

    # Command injection
    if re.search(
        r"(os\.system|subprocess\.call|subprocess\.run)\s*\([^)]*\+|shell\s*=\s*True", code
    ):
        findings.append(
            "SECURITY: Potential command injection. Avoid shell=True and string concatenation."
        )

    # Eval/exec usage
    if re.search(r"\b(eval|exec)\s*\(", code):
        findings.append(
            "SECURITY: Use of eval/exec detected. This can be dangerous with untrusted input."
        )

    # Pickle with untrusted data
    if re.search(r"pickle\.loads?\s*\(", code):
        findings.append("SECURITY: Pickle usage detected. Never unpickle untrusted data.")

    # Hardcoded secrets
    secret_patterns = [
        r"(api_key|apikey|secret|password|token|auth)\s*=\s*['\"][A-Za-z0-9+/=]{16,}['\"]",
        r"(aws_access_key|aws_secret_key)",
    ]
    for pattern in secret_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            findings.append(
                "SECURITY: Possible hardcoded secret detected. Use environment variables or a secrets manager."
            )
            break

    if not findings:
        return "No obvious security issues found."

    return "Security Review:\n\n" + "\n\n".join(f"⚠️ {f}" for f in findings)


@mcp.tool()
def suggest_improvements(code: str, focus: str = "readability") -> str:
    """
    Suggest improvements for the code.

    Args:
        code: The code to improve
        focus: Area to focus on (readability, performance, maintainability)

    Returns:
        Improvement suggestions
    """
    suggestions = []

    if focus in ("readability", "all"):
        # Check for long functions
        lines = code.splitlines()
        in_function = False
        function_lines = 0
        function_name = ""

        for line in lines:
            if re.match(r"\s*(def|async def)\s+(\w+)", line):
                if in_function and function_lines > 50:
                    suggestions.append(
                        f"Function '{function_name}' is {function_lines} lines long. "
                        "Consider breaking it into smaller functions."
                    )
                match = re.match(r"\s*(def|async def)\s+(\w+)", line)
                function_name = match.group(2) if match else ""
                in_function = True
                function_lines = 0
            elif in_function:
                function_lines += 1

        # Check for complex conditions
        if re.search(r"if .+ and .+ and .+ and", code):
            suggestions.append(
                "Complex condition detected. Consider extracting to a well-named function."
            )

    if focus in ("performance", "all"):
        # Check for list concatenation in loops
        if re.search(r"for .+ in .+:\s*\n\s*\w+\s*\+=\s*\[", code):
            suggestions.append(
                "List concatenation in loop detected. Consider using list.extend() or list comprehension."
            )

        # Check for repeated function calls in loops
        if re.search(r"for .+ in .+:\s*\n\s*.*len\(", code):
            suggestions.append(
                "len() called inside loop. Consider caching the length before the loop."
            )

    if not suggestions:
        return f"No specific {focus} improvements suggested. Code looks well-written!"

    return f"Improvement Suggestions ({focus}):\n\n" + "\n\n".join(f"💡 {s}" for s in suggestions)


@mcp.tool()
def review_file(file_path: str) -> str:
    """
    Review a file from disk.

    Args:
        file_path: Path to the file to review

    Returns:
        Comprehensive review of the file
    """
    path = Path(file_path)
    if not path.exists():
        return f"Error: File not found: {file_path}"

    try:
        code = path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"

    # Determine language from extension
    ext = path.suffix.lower()
    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go"}
    language = lang_map.get(ext, "unknown")

    results = []
    results.append(f"# Code Review: {file_path}\n")
    results.append(f"Language: {language}")
    results.append(f"Lines: {len(code.splitlines())}")
    results.append("\n---\n")

    # Run all checks
    results.append("## Code Quality\n")
    results.append(review_code(code, language))

    results.append("\n## Security Check\n")
    results.append(check_security(code))

    results.append("\n## Improvement Suggestions\n")
    results.append(suggest_improvements(code, "all"))

    return "\n".join(results)


# ============== Resources ==============


@mcp.resource("reviewer://guidelines")
def get_review_guidelines() -> str:
    """Get code review guidelines followed by this agent."""
    return """Code Review Guidelines:

1. **Code Quality**
   - Functions should be focused and do one thing
   - Avoid deep nesting (max 3 levels)
   - Use meaningful variable and function names
   - Keep functions under 50 lines when possible

2. **Security**
   - Never hardcode credentials
   - Use parameterized queries for database operations
   - Validate and sanitize all user input
   - Avoid eval/exec with untrusted data

3. **Documentation**
   - All public functions need docstrings
   - Complex logic should have inline comments
   - Keep comments up to date with code

4. **Performance**
   - Avoid premature optimization
   - But watch for obvious inefficiencies
   - Cache expensive computations
   - Use appropriate data structures
"""


# ============== Main ==============


if __name__ == "__main__":
    print("Starting Code Reviewer Agent MCP Server...")
    print("The platform will connect to this agent at http://localhost:8002/mcp")
    mcp.run(transport="streamable-http")
