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


def _process_node_list(nodes, lines, metadata, chunk_size, chunk_overlap, block_start_line, block_end_line, prefix=""):
    chunk_docs = []
    symbols = []
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)
            if start_line and end_line:
                symbols.append((start_line, end_line, prefix + node.name, "classdef", node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)
            if start_line and end_line:
                symbols.append((start_line, end_line, prefix + node.name, "function", node))
                
    if not symbols:
        # entire block is just statements, check size
        block_text = _slice_lines(lines, block_start_line, block_end_line)
        if len(block_text) > chunk_size:
            for part in _chunk_text_by_chars(block_text, chunk_size, chunk_overlap):
                if len(part.strip()) >= MIN_CHUNK_LENGTH:
                    chunk_docs.append(_doc_with_quality(part, metadata, "module", start_line=block_start_line, end_line=block_end_line))
        else:
            if len(block_text.strip()) >= MIN_CHUNK_LENGTH:
                chunk_docs.append(_doc_with_quality(block_text, metadata, "module", start_line=block_start_line, end_line=block_end_line))
        return chunk_docs

    current_line = block_start_line

    for start_line, end_line, symbol_name, symbol_type, node in sorted(symbols, key=lambda s: s[0]):
        if current_line < start_line:
            module_prefix = _slice_lines(lines, current_line, start_line - 1)
            if module_prefix and len(module_prefix.strip()) >= MIN_CHUNK_LENGTH:
                if len(module_prefix) > chunk_size:
                    for part in _chunk_text_by_chars(module_prefix, chunk_size, chunk_overlap):
                        if len(part.strip()) >= MIN_CHUNK_LENGTH:
                            chunk_docs.append(_doc_with_quality(part, metadata, "module", start_line=current_line, end_line=start_line - 1))
                else:
                    chunk_docs.append(_doc_with_quality(module_prefix, metadata, "module", start_line=current_line, end_line=start_line - 1))

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
                # It's too big. Can we recurse?
                if symbol_type == "classdef" and hasattr(node, "body"):
                    child_docs = _process_node_list(node.body, lines, metadata, chunk_size, chunk_overlap, start_line, end_line, prefix=symbol_name + ".")
                    chunk_docs.extend(child_docs)
                else:
                    # Function is too big, fallback to char split
                    for part in _chunk_text_by_chars(symbol_source, chunk_size, chunk_overlap):
                        if len(part.strip()) >= MIN_CHUNK_LENGTH:
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

    if current_line <= block_end_line:
        module_suffix = _slice_lines(lines, current_line, block_end_line)
        if module_suffix and len(module_suffix.strip()) >= MIN_CHUNK_LENGTH:
            if len(module_suffix) > chunk_size:
                for part in _chunk_text_by_chars(module_suffix, chunk_size, chunk_overlap):
                    if len(part.strip()) >= MIN_CHUNK_LENGTH:
                        chunk_docs.append(_doc_with_quality(part, metadata, "module", start_line=current_line, end_line=block_end_line))
            else:
                chunk_docs.append(
                    _doc_with_quality(
                        module_suffix,
                        metadata,
                        "module",
                        start_line=current_line,
                        end_line=block_end_line,
                    )
                )

    return chunk_docs


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
    return _process_node_list(tree.body, lines, metadata, chunk_size, chunk_overlap, 1, len(lines))


def _is_python_document(metadata: dict) -> bool:
    path = (metadata or {}).get("path") or (metadata or {}).get("filename")
    if not path:
        return False
    return os.path.splitext(str(path))[1].lower() == ".py"


def chunk_documents_with_ast(
    documents: Iterable[Document],
    chunk_size: int = 1500,
    chunk_overlap: int = 150,
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