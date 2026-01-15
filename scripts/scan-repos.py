#!/usr/bin/env python3
"""
Cross-Repository Pattern Scanner

Scans all handoffs in the golden library to extract reusable patterns.
Builds a searchable index of code snippets, solutions, and design decisions.

Usage:
    python3 scan-repos.py                    # Scan all handoffs
    python3 scan-repos.py --limit 100        # Scan first 100 handoffs
    python3 scan-repos.py --update           # Update existing index
"""

import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    from qastone_compressor import decompress_v4z
    from v4z_decoder import V4ZDecoder
except ImportError:
    print("Warning: Could not import decompression modules. Will try subprocess fallback.")
    decompress_v4z = None
    V4ZDecoder = None

# Paths
GOLDEN_LIBRARY_DIR = Path.home() / "ztgi" / "golden_library" / ".golden_library"
GOLDEN_INDEX_FILE = GOLDEN_LIBRARY_DIR / "index.json"
COMPRESSED_DIR = GOLDEN_LIBRARY_DIR / "compressed"
PATTERN_INDEX_FILE = GOLDEN_LIBRARY_DIR / "cross_repo_index.json"

# Pattern categories and their keyword triggers
PATTERN_CATEGORIES = {
    "auth": ["authentication", "auth", "login", "jwt", "token", "session", "oauth", "credentials"],
    "websocket": ["websocket", "ws://", "wss://", "real-time", "live update", "socket.io"],
    "3d": ["three.js", "threejs", "webgl", "3d visualization", "scene", "camera", "renderer"],
    "database": ["database", "db", "sql", "query", "index", "schema", "migration"],
    "compression": ["compression", "compress", "v4z", "slim", "fsl", "zstandard", "gzip"],
    "api": ["api", "endpoint", "/api/", "rest", "flask", "fastapi", "route"],
    "ui": ["ui", "dashboard", "component", "react", "vue", "html", "css"],
    "git": ["git", "hook", "commit", "pre-commit", "github", "workflow"],
    "search": ["search", "index", "grep", "query", "elasticsearch", "fuzzy"],
    "testing": ["test", "pytest", "unittest", "benchmark", "assert", "mock"],
    "performance": ["performance", "optimize", "benchmark", "fps", "latency", "cache"],
    "cli": ["cli", "command line", "argparse", "click", "terminal"],
}


@dataclass
class CodeSnippet:
    """A code snippet extracted from a handoff."""
    content: str
    language: str
    start_line: int
    end_line: int
    context_before: str = ""
    context_after: str = ""


@dataclass
class Pattern:
    """A reusable pattern found in a handoff."""
    pattern_id: str          # hash(handoff_id + snippet_hash)
    handoff_id: str          # Source handoff
    category: str            # Pattern category (auth, websocket, etc.)
    tags: List[str]          # Specific tags (jwt, oauth, three.js, etc.)
    title: str               # Pattern title (extracted from context)
    description: str         # Pattern description
    snippet: Optional[CodeSnippet] = None  # Code snippet if applicable
    context: str = ""        # Surrounding markdown context
    repo: str = ""           # Source repository
    created: str = ""        # When handoff was created
    file_path: str = ""      # Original file if known


def load_golden_index() -> Dict:
    """Load the golden library index."""
    if not GOLDEN_INDEX_FILE.exists():
        return {"version": "1.0", "handoffs": []}

    with open(GOLDEN_INDEX_FILE) as f:
        return json.load(f)


def decompress_handoff(handoff_id: str, compressed_file: str) -> Optional[str]:
    """Decompress a V4Z handoff file."""
    # Try direct file read first (for legacy .md files)
    compressed_path = Path(compressed_file)
    if not compressed_path.is_absolute():
        compressed_path = GOLDEN_LIBRARY_DIR / compressed_file

    # Legacy .md file - just read it
    if compressed_path.suffix == '.md':
        if compressed_path.exists():
            return compressed_path.read_text()
        return None

    # V4Z compressed file
    if not compressed_path.exists():
        # Try alternate path
        compressed_path = COMPRESSED_DIR / f"{handoff_id}.v4z"
        if not compressed_path.exists():
            return None

    # Try Python decompression
    if decompress_v4z:
        try:
            decoder = V4ZDecoder()
            with open(compressed_path, 'rb') as f:
                compressed_data = f.read()
            return decoder.decompress(compressed_data)
        except Exception as e:
            print(f"Warning: Python decompression failed for {handoff_id}: {e}")

    # Fallback to subprocess
    try:
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "src" / "decompress.py"), handoff_id],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        print(f"Warning: Subprocess decompression failed for {handoff_id}: {e}")

    return None


def extract_code_blocks(content: str) -> List[CodeSnippet]:
    """Extract code blocks from markdown content."""
    snippets = []
    lines = content.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect code block start
        if line.startswith('```'):
            language = line[3:].strip() or 'text'
            start_line = i
            code_lines = []
            i += 1

            # Collect code block content
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1

            end_line = i

            # Extract context before (previous 3 lines)
            context_before = '\n'.join(lines[max(0, start_line - 3):start_line])

            # Extract context after (next 3 lines)
            context_after = '\n'.join(lines[end_line + 1:min(len(lines), end_line + 4)])

            snippet = CodeSnippet(
                content='\n'.join(code_lines),
                language=language,
                start_line=start_line,
                end_line=end_line,
                context_before=context_before,
                context_after=context_after
            )
            snippets.append(snippet)

        i += 1

    return snippets


def detect_patterns(content: str, handoff: Dict) -> List[Pattern]:
    """Detect patterns in handoff content."""
    patterns = []

    # Extract code blocks
    code_snippets = extract_code_blocks(content)

    # Check for pattern keywords in content
    content_lower = content.lower()
    matched_categories = set()
    matched_tags = set()

    for category, keywords in PATTERN_CATEGORIES.items():
        for keyword in keywords:
            if keyword.lower() in content_lower:
                matched_categories.add(category)
                matched_tags.add(keyword)

    # If no patterns detected, skip
    if not matched_categories:
        return patterns

    # For each matched category, create pattern entries
    for category in matched_categories:
        # Find relevant snippets for this category
        category_keywords = PATTERN_CATEGORIES[category]
        relevant_snippets = []

        for snippet in code_snippets:
            snippet_lower = snippet.content.lower()
            context_lower = (snippet.context_before + snippet.context_after).lower()

            # Check if snippet is relevant to category
            for keyword in category_keywords:
                if keyword.lower() in snippet_lower or keyword.lower() in context_lower:
                    relevant_snippets.append(snippet)
                    break

        # Create pattern for each relevant snippet
        for snippet in relevant_snippets:
            # Extract title from context
            title = extract_title_from_context(snippet.context_before, category)

            # Generate pattern ID
            import hashlib
            snippet_hash = hashlib.sha256(snippet.content.encode()).hexdigest()[:12]
            pattern_id = f"{handoff.get('handoff_id', 'unknown')}_{snippet_hash}"

            # Get category-specific tags
            snippet_tags = [tag for tag in matched_tags if tag in PATTERN_CATEGORIES[category]]

            pattern = Pattern(
                pattern_id=pattern_id,
                handoff_id=handoff.get('handoff_id', 'unknown'),
                category=category,
                tags=list(snippet_tags),
                title=title or f"{category.title()} Implementation",
                description=snippet.context_before.strip()[-200:] if snippet.context_before else "",
                snippet=snippet,
                context=snippet.context_before + "\n\n" + snippet.context_after,
                repo=extract_repo_from_handoff(handoff),
                created=handoff.get('created', ''),
                file_path=handoff.get('source_file', handoff.get('original_file', ''))
            )
            patterns.append(pattern)

        # Also create a pattern for the category itself (without code)
        if matched_categories and not relevant_snippets:
            # Extract relevant text section
            section_text = extract_category_section(content, category)

            if section_text:
                title = extract_title_from_context(section_text, category)

                import hashlib
                section_hash = hashlib.sha256(section_text.encode()).hexdigest()[:12]
                pattern_id = f"{handoff.get('handoff_id', 'unknown')}_{section_hash}"

                snippet_tags = [tag for tag in matched_tags if tag in PATTERN_CATEGORIES[category]]

                pattern = Pattern(
                    pattern_id=pattern_id,
                    handoff_id=handoff.get('handoff_id', 'unknown'),
                    category=category,
                    tags=list(snippet_tags),
                    title=title or f"{category.title()} Discussion",
                    description=section_text[:300],
                    snippet=None,
                    context=section_text,
                    repo=extract_repo_from_handoff(handoff),
                    created=handoff.get('created', ''),
                    file_path=handoff.get('source_file', handoff.get('original_file', ''))
                )
                patterns.append(pattern)

    return patterns


def extract_title_from_context(context: str, category: str) -> str:
    """Extract a title from surrounding context."""
    lines = context.strip().split('\n')

    # Look for markdown headers
    for line in reversed(lines):
        if line.startswith('#'):
            return line.lstrip('#').strip()

    # Look for task list items
    for line in reversed(lines):
        if line.strip().startswith('- ['):
            return line.split(']', 1)[1].strip()

    # Look for bold text
    for line in reversed(lines):
        bold_match = re.search(r'\*\*(.+?)\*\*', line)
        if bold_match:
            return bold_match.group(1)

    # Fallback: first non-empty line
    for line in reversed(lines):
        if line.strip():
            return line.strip()[:50]

    return f"{category.title()} Pattern"


def extract_category_section(content: str, category: str) -> str:
    """Extract relevant section of content for a category."""
    lines = content.split('\n')
    keywords = PATTERN_CATEGORIES[category]

    # Find lines mentioning category keywords
    relevant_indices = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        for keyword in keywords:
            if keyword.lower() in line_lower:
                relevant_indices.append(i)
                break

    if not relevant_indices:
        return ""

    # Take first match and extract ±10 lines
    first_match = relevant_indices[0]
    start = max(0, first_match - 10)
    end = min(len(lines), first_match + 10)

    return '\n'.join(lines[start:end])


def extract_repo_from_handoff(handoff: Dict) -> str:
    """Extract repository name from handoff metadata."""
    # Try to get from repository field
    repo = handoff.get('repository', '')
    if repo:
        return Path(repo).name

    # Try to infer from file path
    source_file = handoff.get('source_file', handoff.get('original_file', ''))
    if source_file and '/ztgi/' in source_file:
        parts = source_file.split('/ztgi/')
        if len(parts) > 1:
            repo_parts = parts[1].split('/')
            if repo_parts:
                return repo_parts[0]

    return "unknown"


def scan_handoffs(limit: Optional[int] = None) -> List[Pattern]:
    """Scan all handoffs and extract patterns."""
    index = load_golden_index()
    handoffs = index.get('handoffs', [])

    if limit:
        handoffs = handoffs[:limit]

    all_patterns = []

    print(f"Scanning {len(handoffs)} handoffs for patterns...")

    for i, handoff in enumerate(handoffs):
        handoff_id = handoff.get('handoff_id', 'unknown')
        compressed_file = handoff.get('compressed_file', f"compressed/{handoff_id}.v4z")

        # Progress indicator
        if (i + 1) % 50 == 0:
            print(f"  Processed {i + 1}/{len(handoffs)} handoffs, found {len(all_patterns)} patterns...")

        # Decompress handoff
        content = decompress_handoff(handoff_id, compressed_file)
        if not content:
            continue

        # Extract patterns
        patterns = detect_patterns(content, handoff)
        all_patterns.extend(patterns)

    print(f"\nFound {len(all_patterns)} patterns across {len(handoffs)} handoffs")

    # Print category breakdown
    category_counts = {}
    for pattern in all_patterns:
        category_counts[pattern.category] = category_counts.get(pattern.category, 0) + 1

    print("\nPatterns by category:")
    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {category}: {count}")

    return all_patterns


def save_pattern_index(patterns: List[Pattern]):
    """Save pattern index to JSON."""
    # Convert patterns to dict
    pattern_dicts = []
    for pattern in patterns:
        pattern_dict = {
            "pattern_id": pattern.pattern_id,
            "handoff_id": pattern.handoff_id,
            "category": pattern.category,
            "tags": pattern.tags,
            "title": pattern.title,
            "description": pattern.description,
            "repo": pattern.repo,
            "created": pattern.created,
            "file_path": pattern.file_path,
            "context": pattern.context[:500],  # Limit context size
        }

        # Add snippet if present
        if pattern.snippet:
            pattern_dict["snippet"] = {
                "content": pattern.snippet.content,
                "language": pattern.snippet.language,
                "start_line": pattern.snippet.start_line,
                "end_line": pattern.snippet.end_line,
            }

        pattern_dicts.append(pattern_dict)

    # Create index structure
    index = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "total_patterns": len(patterns),
        "categories": list(PATTERN_CATEGORIES.keys()),
        "patterns": pattern_dicts
    }

    # Save to file
    PATTERN_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PATTERN_INDEX_FILE, 'w') as f:
        json.dump(index, f, indent=2)

    print(f"\nPattern index saved to {PATTERN_INDEX_FILE}")
    print(f"Total patterns: {len(patterns)}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Scan repositories for reusable patterns")
    parser.add_argument('--limit', type=int, help="Limit number of handoffs to scan")
    parser.add_argument('--update', action='store_true', help="Update existing index")

    args = parser.parse_args()

    # Scan handoffs
    patterns = scan_handoffs(limit=args.limit)

    # Save index
    save_pattern_index(patterns)

    print("\nDone! Pattern index ready for search.")


if __name__ == '__main__':
    main()
