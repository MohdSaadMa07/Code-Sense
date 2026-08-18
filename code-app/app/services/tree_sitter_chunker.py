import os
import re
from html.parser import HTMLParser
from typing import Callable

from langchain_core.documents import Document

try:
    from tree_sitter_languages import get_parser as tree_sitter_get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when dependency is not installed
    TREE_SITTER_AVAILABLE = False

    def tree_sitter_get_parser(_language: str):
        raise RuntimeError("tree-sitter is not installed")


EXTENSION_LANGUAGE_MAP = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "c_sharp",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".py": "python",
    ".pyi": "python",
}


def _build_doc(content: str, metadata: dict, chunk_type: str, **extra_metadata) -> Document:
    next_metadata = dict(metadata or {})
    next_metadata["chunk_type"] = chunk_type
    next_metadata.update(extra_metadata)
    return Document(page_content=content, metadata=next_metadata)


def _parse_quality_for_chunk_type(chunk_type: str) -> str:
    if chunk_type in {"ast", "tree_sitter", "html_table_headers"}:
        return "high"
    if chunk_type == "module":
        return "medium"
    return "low"


def _doc_with_quality(content: str, metadata: dict, chunk_type: str, **extra_metadata) -> Document:
    if "parse_quality" not in extra_metadata:
        extra_metadata["parse_quality"] = _parse_quality_for_chunk_type(chunk_type)
    return _build_doc(content, metadata, chunk_type, **extra_metadata)


def _resolve_path(metadata: dict) -> str:
    return (metadata or {}).get("path") or (metadata or {}).get("filename") or ""


def _language_for_path(path: str) -> str | None:
    ext = os.path.splitext(path)[1].lower()
    return EXTENSION_LANGUAGE_MAP.get(ext)


class _TableHeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_th = False
        self._buffer: list[str] = []
        self.headers: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "th":
            self._in_th = True
            self._buffer = []

    def handle_data(self, data):
        if self._in_th:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "th" and self._in_th:
            text = " ".join("".join(self._buffer).split())
            if text:
                self.headers.append(text)
            self._in_th = False
            self._buffer = []


def _extract_html_table_header_docs(text: str, metadata: dict) -> list[Document]:
    parser = _TableHeaderParser()
    try:
        parser.feed(text)
    except Exception:
        return []

    if not parser.headers:
        return []

    # Deduplicate while preserving order.
    seen = set()
    ordered_headers = []
    for header in parser.headers:
        lower = header.lower()
        if lower in seen:
            continue
        seen.add(lower)
        ordered_headers.append(header)

    header_text = "Table columns: " + ", ".join(ordered_headers)
    return [
        _doc_with_quality(
            header_text,
            metadata,
            "html_table_headers",
            language="html",
            node_type="th",
        )
    ]


def _clean_markdown_for_ingestion(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue

        if re.match(r"^!?\[[^\]]*\]\([^)]*\)$", line):
            continue
        if line.startswith("!"):
            continue
        if line.startswith("---"):
            continue

        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line)

        alnum_count = sum(ch.isalnum() for ch in line)
        if alnum_count < 3:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _extract_recursive_nodes(node, source_bytes, chunk_size, chunk_overlap, char_splitter, metadata, language):
    chunk_docs = []
    
    node_text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore").strip()
    if not node_text:
        return []
    
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    
    if len(node_text) <= chunk_size:
        chunk_docs.append(
            _doc_with_quality(
                node_text,
                metadata,
                "tree_sitter",
                language=language,
                node_type=node.type,
                start_line=start_line,
                end_line=end_line,
            )
        )
        return chunk_docs

    children = [c for c in node.named_children if c.end_byte > c.start_byte]
    
    if not children:
        for part in char_splitter(node_text, chunk_size, chunk_overlap):
            chunk_docs.append(
                _doc_with_quality(
                    part,
                    metadata,
                    "tree_sitter_fallback",
                    language=language,
                    node_type=node.type,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
        return chunk_docs

    current_group_start_byte = None
    current_group_end_byte = None
    group_type = "mixed"
    group_start_line = None
    group_end_line = None

    def emit_group():
        nonlocal current_group_start_byte, current_group_end_byte
        if current_group_start_byte is not None and current_group_end_byte is not None:
            text = source_bytes[current_group_start_byte:current_group_end_byte].decode("utf-8", errors="ignore").strip()
            if text:
                chunk_docs.append(
                    _doc_with_quality(
                        text,
                        metadata,
                        "tree_sitter",
                        language=language,
                        node_type=group_type,
                        start_line=group_start_line,
                        end_line=group_end_line,
                    )
                )
        current_group_start_byte = None
        current_group_end_byte = None

    for child in children:
        child_len = child.end_byte - child.start_byte
        if child_len > chunk_size:
            emit_group()
            chunk_docs.extend(_extract_recursive_nodes(child, source_bytes, chunk_size, chunk_overlap, char_splitter, metadata, language))
        else:
            if current_group_start_byte is None:
                current_group_start_byte = child.start_byte
                current_group_end_byte = child.end_byte
                group_type = child.type
                group_start_line = child.start_point[0] + 1
                group_end_line = child.end_point[0] + 1
            else:
                if child.end_byte - current_group_start_byte > chunk_size:
                    emit_group()
                    current_group_start_byte = child.start_byte
                    current_group_end_byte = child.end_byte
                    group_type = child.type
                    group_start_line = child.start_point[0] + 1
                    group_end_line = child.end_point[0] + 1
                else:
                    current_group_end_byte = child.end_byte
                    group_end_line = child.end_point[0] + 1

    emit_group()
    return chunk_docs


def chunk_with_tree_sitter(
    text: str,
    metadata: dict,
    chunk_size: int,
    chunk_overlap: int,
    char_splitter: Callable[[str, int, int], list[str]],
) -> list[Document]:
    path = _resolve_path(metadata)
    ext = os.path.splitext(path)[1].lower()
    language = _language_for_path(path)

    working_text = text
    if ext == ".md":
        cleaned = _clean_markdown_for_ingestion(text)
        if cleaned:
            working_text = cleaned

    html_header_docs = []
    if ext in {".html", ".htm"}:
        html_header_docs = _extract_html_table_header_docs(working_text, metadata)

    if language is None or not TREE_SITTER_AVAILABLE:
        fallback_docs = [
            _doc_with_quality(chunk, metadata, "fallback", fallback_reason="unsupported_or_not_installed")
            for chunk in char_splitter(working_text, chunk_size, chunk_overlap)
        ]
        return html_header_docs + fallback_docs

    try:
        parser = tree_sitter_get_parser(language)
        source_bytes = working_text.encode("utf-8")
        tree = parser.parse(source_bytes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("DEBUG TREE SITTER EXCEPTION:", type(e), e)
        fallback_docs = [
            _doc_with_quality(chunk, metadata, "fallback", fallback_reason="tree_sitter_parse_error")
            for chunk in char_splitter(working_text, chunk_size, chunk_overlap)
        ]
        return html_header_docs + fallback_docs

    root = tree.root_node
    chunk_docs = _extract_recursive_nodes(
        root, source_bytes, chunk_size, chunk_overlap, char_splitter, metadata, language
    )

    if not chunk_docs:
        fallback_docs = [
            _doc_with_quality(chunk, metadata, "fallback", fallback_reason="tree_sitter_empty_chunks")
            for chunk in char_splitter(working_text, chunk_size, chunk_overlap)
        ]
        return html_header_docs + fallback_docs

    return html_header_docs + chunk_docs
