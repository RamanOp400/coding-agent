from langchain_community.tools import DuckDuckGoSearchRun,ShellTool
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_community.tools import ReadFileTool, WriteFileTool, ListDirectoryTool, CopyFileTool, MoveFileTool, FileSearchTool
from langchain_core.tools import tool
from datetime import datetime
import pytz
import os
import shutil

@tool
def get_current_date_tool()->dict:
    """return current date, time, and day for Asia/Kolkata timezone"""
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(kolkata_tz)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day": now.strftime("%A")
    }
@tool 
def web_search(query: str) -> str:
    """Search the web for information using DuckDuckGo. Use this when you need to find documentation, solutions, or any online information."""
    search = DuckDuckGoSearchRun()
    return search.run(query)

# --- Shell Tool ---
shell_tool = ShellTool()
shell_tool.description = "Run shell commands on the system. Use for: installing packages, running tests, git operations, executing scripts. Always be cautious with destructive commands."

# --- File Management Tools ---
# These tools operate relative to the working directory (root_dir)
file_toolkit = FileManagementToolkit(
    root_dir=".",  # change this to the target project directory at runtime
    selected_tools=["read_file", "write_file", "list_directory", "copy_file", "move_file", "file_search"]
)
file_tools = file_toolkit.get_tools()

# --- Custom tools that FileManagementToolkit doesn't provide ---

@tool
def delete_file(file_path: str) -> str:
    """Delete a file or an empty directory. Use with caution — this is irreversible."""
    try:
        if os.path.isfile(file_path):
            os.remove(file_path)
            return f"Deleted file: {file_path}"
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return f"Deleted directory: {file_path}"
        else:
            return f"Path not found: {file_path}"
    except Exception as e:
        return f"Error deleting {file_path}: {e}"

@tool
def create_directory(dir_path: str) -> str:
    """Create a new directory (including parent directories if needed). Use for scaffolding project structure."""
    try:
        os.makedirs(dir_path, exist_ok=True)
        return f"Created directory: {dir_path}"
    except Exception as e:
        return f"Error creating directory: {e}"

@tool
def read_lines(file_path: str, start_line: int, end_line: int) -> str:
    """Read specific line range from a file (1-indexed, inclusive). Use this for large files instead of reading the entire file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        selected = lines[start_line - 1 : end_line]
        result = ""
        for i, line in enumerate(selected, start=start_line):
            result += f"{i}: {line}"
        return result
    except Exception as e:
        return f"Error reading lines: {e}"

@tool
def find_and_replace(file_path: str, find_text: str, replace_text: str) -> str:
    """Find and replace text in a file. Use for targeted edits without rewriting the entire file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        count = content.count(find_text)
        if count == 0:
            return f"Text not found in {file_path}"
        new_content = content.replace(find_text, replace_text)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Replaced {count} occurrence(s) in {file_path}"
    except Exception as e:
        return f"Error: {e}"

@tool
def directory_tree(dir_path: str, max_depth: int = 3) -> str:
    """Show the recursive directory tree structure. Use to understand project layout before making changes."""
    tree_lines = []
    def _walk(path, prefix, depth):
        if depth > max_depth:
            return
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return
        dirs = [e for e in entries if os.path.isdir(os.path.join(path, e)) and not e.startswith('.')]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]
        for f in files:
            tree_lines.append(f"{prefix} {f}")
        for d in dirs:
            tree_lines.append(f"{prefix} {d}/")
            _walk(os.path.join(path, d), prefix + "  ", depth + 1)
    tree_lines.append(f"{dir_path}/")
    _walk(dir_path, "  ", 1)
    return "\n".join(tree_lines)

# --- Claude Code-style tools ---

@tool
def glob_find(pattern: str, root_dir: str = ".") -> str:
    """Find files matching a glob pattern recursively. Like Claude Code's Glob tool.
    Examples: '**/*.py' finds all Python files, 'src/**/*.ts' finds TypeScript files under src/,
    '*.{json,yaml}' finds JSON and YAML files in current dir."""
    import glob as glob_module
    try:
        matches = glob_module.glob(pattern, root_dir=root_dir, recursive=True)
        matches.sort(key=lambda f: os.path.getmtime(os.path.join(root_dir, f)) if os.path.exists(os.path.join(root_dir, f)) else 0, reverse=True)
        if len(matches) > 100:
            return "\n".join(matches[:100]) + f"\n\n... truncated ({len(matches)} total). Use a more specific pattern."
        if not matches:
            return f"No files found matching pattern: {pattern}"
        return "\n".join(matches)
    except Exception as e:
        return f"Error: {e}"

@tool
def grep_in_files(pattern: str, path: str = ".", file_filter: str = "") -> str:
    """Search for a text pattern across files recursively. Like Claude Code's Grep tool.
    Searches file contents (not filenames). Use file_filter to limit to specific types e.g. '*.py'.
    Returns matching lines with file path and line number."""
    import re
    results = []
    try:
        for root, dirs, files in os.walk(path):
            # skip hidden dirs and common noise
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', '.git', 'venv')]
            for fname in files:
                if file_filter and not fname.endswith(file_filter.replace("*", "")):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(pattern, line):
                                results.append(f"{fpath}:{i}: {line.rstrip()}")
                                if len(results) >= 50:
                                    return "\n".join(results) + "\n\n... truncated at 50 matches."
                except (PermissionError, IsADirectoryError):
                    continue
        if not results:
            return f"No matches found for pattern: {pattern}"
        return "\n".join(results)
    except Exception as e:
        return f"Error: {e}"

@tool
def fetch_url(url: str) -> str:
    """Fetch content from a URL and return it as text. Like Claude Code's WebFetch tool.
    Use for reading documentation, API references, or any web page content."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            content = response.read().decode("utf-8", errors="ignore")
            # Return first 5000 chars to avoid flooding context
            if len(content) > 5000:
                return content[:5000] + f"\n\n... truncated ({len(content)} chars total)"
            return content
    except Exception as e:
        return f"Error fetching {url}: {e}"

# --- Collect all tools for binding to the LLM ---
all_tools = [
    get_current_date_tool,
    web_search,
    shell_tool,
    *file_tools,  # read_file, write_file, list_directory, copy_file, move_file, file_search
    delete_file,
    create_directory,
    read_lines,
    find_and_replace,
    directory_tree,
    glob_find,
    grep_in_files,
    fetch_url,
]
