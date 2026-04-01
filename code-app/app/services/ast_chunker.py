import ast
import os
from typing import Iterable

from langchain_core.documents import Document
from app.services.tree_sitter_chunker import chunk_with_tree_sitter

# Chunks shorter than this are stray comments / single lines that cause hallucination
MIN_CHUNK_LENGTH = 80


def _chunk_text_by_chars(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    overlap = max(0, min(chunk_overlap, chunk_size - 1))
    step = chunk_size - overlap

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start += step

    return chunks


def _build_doc(content: str, metadata: dict, chunk_type: str, **extra_metadata) -> Document:
    next_metadata = dict(metadata or {})
    next_metadata["chunk_type"] = chunk_type
    next_metadata.update(extra_metadata)
    return Document(page_content=content, metadata=next_metadata)


def _parse_quality_for_chunk_type(chunk_type: str) -> str:
    if chunk_type == "ast":
        return "high"
    if chunk_type == "module":
        return "medium"
    return "low"


def _doc_with_quality(content: str, metadata: dict, chunk_type: str, **extra_metadata) -> Document:
    if "parse_quality" not in extra_metadata:
        extra_metadata["parse_quality"] = _parse_quality_for_chunk_type(chunk_type)
    return _build_doc(content, metadata, chunk_type, **extra_metadata)


def _slice_lines(lines: list[str], start_line: int, end_line: int) -> str:
    return "".join(lines[start_line - 1:end_line]).strip()


def _python_ast_chunks(text: str, metadata: dict, chunk_size: int, chunk_overlap: int) -> list[Document]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [
            _doc_with_quality(chunk, metadata, "fallback")
            for chunk in _chunk_text_by_chars(text, chunk_size, chunk_overlap)
            if len(chunk.strip()) >= MIN_CHUNK_LENGTH  # ✅ skip short chunks
        ]

    lines = text.splitlines(keepends=True)
    chunk_docs: list[Document] = []

    symbols: list[tuple[int, int, str, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)
            if start_line and end_line:
                symbols.append((start_line, end_line, node.name, node.__class__.__name__.lower()))

    if not symbols:
        return [
            _doc_with_quality(chunk, metadata, "module")
            for chunk in _chunk_text_by_chars(text, chunk_size, chunk_overlap)
            if len(chunk.strip()) >= MIN_CHUNK_LENGTH  # ✅ skip short chunks
        ]

    current_line = 1
    total_lines = len(lines)

    for start_line, end_line, symbol_name, symbol_type in sorted(symbols, key=lambda s: s[0]):
        if current_line < start_line:
            module_prefix = _slice_lines(lines, current_line, start_line - 1)
            # ✅ FIX: skip stray comments between symbols (e.g. "#for updating status of order")
            if module_prefix and len(module_prefix.strip()) >= MIN_CHUNK_LENGTH:
                chunk_docs.append(
                    _doc_with_quality(
                        module_prefix,
                        metadata,
                        "module",
                        start_line=current_line,
                        end_line=start_line - 1,
                    )
                )

        symbol_source = _slice_lines(lines, start_line, end_line)
        if symbol_source:
            if len(symbol_source) <= chunk_size:
                chunk_docs.append(
                    _doc_with_quality(
                        symbol_source,
                        metadata,
                        "ast",
                        symbol=symbol_name,
                        symbol_kind=symbol_type,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
            else:
                for part in _chunk_text_by_chars(symbol_source, chunk_size, chunk_overlap):
                    if len(part.strip()) >= MIN_CHUNK_LENGTH:  # ✅ skip short sub-parts
                        chunk_docs.append(
                            _doc_with_quality(
                                part,
                                metadata,
                                "ast",
                                symbol=symbol_name,
                                symbol_kind=symbol_type,
                                start_line=start_line,
                                end_line=end_line,
                            )
                        )

        current_line = max(current_line, end_line + 1)

    if current_line <= total_lines:
        module_suffix = _slice_lines(lines, current_line, total_lines)
        if module_suffix and len(module_suffix.strip()) >= MIN_CHUNK_LENGTH:  # ✅ skip short suffix
            chunk_docs.append(
                _doc_with_quality(
                    module_suffix,
                    metadata,
                    "module",
                    start_line=current_line,
                    end_line=total_lines,
                )
            )

    return chunk_docs


def _is_python_document(metadata: dict) -> bool:
    path = (metadata or {}).get("path") or (metadata or {}).get("filename")
    if not path:
        return False
    return os.path.splitext(str(path))[1].lower() == ".py"


def chunk_documents_with_ast(
    documents: Iterable[Document],
    chunk_size: int = 1500,   # ✅ FIX: was 500 — too small, truncated README mid-sentence
    chunk_overlap: int = 150,  # ✅ FIX: was 50
) -> list[Document]:
    chunked_docs: list[Document] = []

    for doc in documents:
        content = (doc.page_content or "").strip()
        if not content:
            continue

        metadata = doc.metadata or {}
        if _is_python_document(metadata):
            chunked_docs.extend(_python_ast_chunks(content, metadata, chunk_size, chunk_overlap))
        else:
            chunked_docs.extend(
                chunk_with_tree_sitter(
                    content,
                    metadata,
                    chunk_size,
                    chunk_overlap,
                    _chunk_text_by_chars,
                )
            )

    return chunked_docs