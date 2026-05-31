from __future__ import annotations
import fnmatch
import os
import re
from pathlib import Path

import yaml as _yaml

from tools import ToolContext, tool


# Set of glob patterns matched against the filename (not the full path).
# If matched, access is denied regardless of allowed_paths.
_SENSITIVE_PATTERNS: frozenset[str] = frozenset({
    ".env",
    ".env.*",          # .env.local, .env.production, etc.
    "*.env",           # myapp.env, whatever.env
    "*.env.*",         # something.env.local, something.env.production
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.crt",           # certificates — may contain private keys
    "*.secret",
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "*.kdbx",          # KeePass
    "credentials",     # AWS credentials file
    "config",          # AWS config file (catches ~/.aws/config)
})


def _is_sensitive_file(path: Path) -> bool:
    """Return True if the filename matches a known-sensitive pattern."""
    name = path.name
    return any(fnmatch.fnmatch(name, pattern) for pattern in _SENSITIVE_PATTERNS)


def _is_private_path(path: Path) -> bool:
    """Return True if any segment of the path starts with '_' or '.' (private/system paths)."""
    return any(part.startswith("_") or part.startswith(".") for part in path.parts)


def _assert_path_allowed(path: str, context: ToolContext) -> Path:
    """Resolve path and verify it is under one of context.allowed_paths. Raises PermissionError if not."""
    resolved = Path(path).resolve()
    for allowed in context.allowed_paths:
        if resolved.is_relative_to(Path(allowed).resolve()):
            # Check each segment relative to the allowed root for private prefixes
            rel = resolved.relative_to(Path(allowed).resolve())
            if _is_private_path(rel):
                raise PermissionError(
                    f"Path '{path}' refers to a private or system path (segments starting with '_' or '.' are reserved)."
                )
            # Check if the file is sensitive (e.g., .env, *.key, etc.)
            if _is_sensitive_file(resolved):
                raise PermissionError(
                    f"Path '{path}' refers to a sensitive file that agents cannot access."
                )
            return resolved
    raise PermissionError(f"Path '{path}' is outside allowed paths: {context.allowed_paths}")


@tool
def read_file(path: str, context: ToolContext) -> str:
    """Read a text file and return its contents."""
    try:
        resolved = _assert_path_allowed(path, context)
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    
    if not resolved.exists():
        return f"[ERROR] File not found: {path}"
    
    try:
        return resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return resolved.read_text(encoding="latin-1")
    except Exception as e:
        return f"[ERROR] Failed to read {path}: {str(e)}"


@tool
def write_file(path: str, content: str, context: ToolContext) -> str:
    """Write content to a file, creating parent directories if needed."""
    try:
        resolved = _assert_path_allowed(path, context)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Written: {path}"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to write {path}: {str(e)}"


@tool
def list_files(path: str, context: ToolContext) -> str:
    """List files in a directory. Returns newline-separated relative paths."""
    try:
        resolved = _assert_path_allowed(path, context)
        paths = []
        for root, dirs, files in os.walk(resolved):
            # Prune private directories in-place so os.walk won't descend into them
            dirs[:] = [d for d in dirs if not d.startswith("_") and not d.startswith(".")]
            for filename in files:
                if filename.startswith("_") or filename.startswith("."):
                    continue
                full = Path(root) / filename
                paths.append(str(full.relative_to(resolved)))
        return "\n".join(paths) if paths else "(empty)"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to list {path}: {str(e)}"

@tool
def delete_file(path: str, context: ToolContext) -> str:
    """Delete a file."""
    try:
        resolved = _assert_path_allowed(path, context)
        resolved.unlink()
        return f"Deleted: {path}"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except FileNotFoundError:
        return f"[ERROR] File not found: {path}"
    except Exception as e:
        return f"[ERROR] Failed to delete {path}: {str(e)}"


@tool
def file_exists(path: str, context: ToolContext) -> str:
    """Check if a file exists. Returns 'true' or 'false'."""
    try:
        resolved = _assert_path_allowed(path, context)
        return str(resolved.exists()).lower()
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to check {path}: {str(e)}"


@tool
def read_file_lines(path: str, start_line: int, end_line: int, context: ToolContext) -> str:
    """Read a specific range of lines from a file. Lines are 1-based and inclusive.
    Useful for inspecting a section of a large file without loading all of it."""
    try:
        resolved = _assert_path_allowed(path, context)
        if not resolved.exists():
            return f"[ERROR] File not found: {path}"
        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = resolved.read_text(encoding="latin-1")
        lines = text.splitlines()
        total = len(lines)
        s = max(1, start_line) - 1
        e = min(total, end_line)
        selected = lines[s:e]
        return "\n".join(f"{s + 1 + i}: {line}" for i, line in enumerate(selected))
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to read {path}: {str(e)}"


@tool
def append_to_file(path: str, content: str, context: ToolContext) -> str:
    """Append content to a file without overwriting it. Creates the file if it does not exist."""
    try:
        resolved = _assert_path_allowed(path, context)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended to: {path}"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to append to {path}: {str(e)}"


@tool
def replace_in_file(path: str, old_string: str, new_string: str, context: ToolContext) -> str:
    """Replace exactly one occurrence of old_string with new_string in a file.
    Fails if the string is not found or appears more than once — add more surrounding
    context to old_string to make it unique."""
    try:
        resolved = _assert_path_allowed(path, context)
        if not resolved.exists():
            return f"[ERROR] File not found: {path}"
        try:
            text = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = resolved.read_text(encoding="latin-1")
        count = text.count(old_string)
        if count == 0:
            return f"[ERROR] String not found in {path}"
        if count > 1:
            return f"[ERROR] String appears {count} times in {path} — must be unique. Include more surrounding context in old_string."
        resolved.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
        return f"Replaced 1 occurrence in: {path}"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to replace in {path}: {str(e)}"


@tool
def insert_at_line(path: str, line_number: int, text: str, context: ToolContext) -> str:
    """Insert text before a given 1-based line number in a file.
    Use line_number=1 to prepend. Use line_number equal to (total lines + 1) to append."""
    try:
        resolved = _assert_path_allowed(path, context)
        if not resolved.exists():
            return f"[ERROR] File not found: {path}"
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = resolved.read_text(encoding="latin-1")
        lines = content.splitlines(keepends=True)
        idx = max(0, min(line_number - 1, len(lines)))
        insert_text = text if text.endswith("\n") else text + "\n"
        lines.insert(idx, insert_text)
        resolved.write_text("".join(lines), encoding="utf-8")
        return f"Inserted at line {line_number} in: {path}"
    except PermissionError as e:
        return f"[ERROR] {str(e)}"
    except Exception as e:
        return f"[ERROR] Failed to insert in {path}: {str(e)}"


# Maximum file size to search — prevents runaway reads on large binaries or logs.
_GREP_MAX_FILE_BYTES = 1 * 1024 * 1024  # 1 MB


@tool
def grep_files(
    pattern: str,
    path: str,
    glob: str,
    context: ToolContext,
) -> str:
    """Search for a regex pattern across files matching a glob under path.

    Walks the directory tree rooted at ``path``, filters files by ``glob``
    (e.g. ``**/*.yaml``), and returns every line that matches ``pattern``.

    Output format: one match per line — ``filepath:lineno: content``.
    Returns ``(no matches)`` when nothing is found.

    Files larger than 1 MB are skipped to avoid runaway reads.

    Parameters:
        pattern (str): Python regex pattern (re.search).
        path (str): Root directory to search. Must be within allowed paths.
        glob (str): Filename glob filter applied to each file's name (e.g.
            ``*.yaml``, ``**/*.yaml``).  Only the *filename* component is
            matched against the glob, so ``**/*.yaml`` and ``*.yaml`` behave
            identically here.
        context (ToolContext): Injected by the tool runner; carries allowed
            paths and agent identity.

    Returns:
        str: Newline-separated match lines, or ``(no matches)``, or an error
        string prefixed with ``[ERROR]``.
    """
    try:
        resolved = _assert_path_allowed(path, context)
    except PermissionError as e:
        return f"[ERROR] {str(e)}"

    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return f"[ERROR] Invalid regex pattern: {e}"

    # Derive a simple filename-only glob for fnmatch from the provided glob.
    # Take the last path component so that both "*.yaml" and "**/*.yaml"
    # correctly become "*.yaml" for per-filename matching.
    filename_glob = Path(glob).name or "*"

    matches: list[str] = []

    for root, dirs, files in os.walk(resolved):
        # Prune private directories (same convention as list_files).
        dirs[:] = [
            d for d in dirs
            if not d.startswith("_") and not d.startswith(".")
        ]
        for filename in files:
            if filename.startswith("_") or filename.startswith("."):
                continue
            if not fnmatch.fnmatch(filename, filename_glob):
                continue

            file_path = Path(root) / filename

            if file_path.stat().st_size > _GREP_MAX_FILE_BYTES:
                matches.append(
                    f"[SKIPPED — file too large] {file_path}"
                )
                continue

            try:
                text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                try:
                    text = file_path.read_text(encoding="latin-1")
                except OSError:
                    continue

            for lineno, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    matches.append(f"{file_path}:{lineno}: {line}")

    return "\n".join(matches) if matches else "(no matches)"


@tool
def validate_yaml(path: str, context: ToolContext) -> str:
    """Validate that a file contains well-formed YAML.

    Reads the file at ``path`` and attempts to parse it with PyYAML.
    Returns ``"valid"`` on success, or a human-readable error string
    describing the parse failure (line number and message) so the agent
    can correct the file before committing.

    Parameters:
        path (str): Path to the YAML file to validate. Must be within
            allowed workspace paths.
        context (ToolContext): Injected by the tool runner.

    Returns:
        str: ``"valid"`` if the file parses successfully, otherwise an
        error description prefixed with ``[INVALID YAML]``.
    """
    try:
        resolved = _assert_path_allowed(path, context)
    except PermissionError as e:
        return f"[ERROR] {str(e)}"

    if not resolved.exists():
        return f"[ERROR] File not found: {path}"

    try:
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = resolved.read_text(encoding="latin-1")
    except OSError as e:
        return f"[ERROR] Could not read {path}: {e}"

    try:
        _yaml.safe_load(text)
        return "valid"
    except _yaml.YAMLError as e:
        return f"[INVALID YAML] {path}: {e}"

