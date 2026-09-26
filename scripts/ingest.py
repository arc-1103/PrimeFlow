#!/usr/bin/env python
"""Parse corpus/ -> deterministic chunks -> dense (FAISS) + sparse (BM25) indexes.

Idempotent: re-running against an unchanged corpus reproduces identical
chunk_ids (content-hash based, never incrementing counters) and identical
index contents (AGENTS.md SS2 "No hardcoding / no precomputation" ->
determinism of the *pipeline*, not of outputs).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from docx import Document as DocxDocument
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import settings  # noqa: E402
from app.retrieval.sparse import build_bm25  # noqa: E402

MAX_CHUNK_CHARS = 800
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def chunk_sentences(sentences: list[str], max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Deterministic sentence-aware chunking: accumulate sentences up to
    max_chars, never split a sentence in half. The one place custom chunking
    logic is expected (AGENTS.md SS3) -- no off-the-shelf chunker fits every
    corpus shape.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        if current and current_len + len(sentence) + 1 > max_chars:
            chunks.append(" ".join(current))
            current, current_len = [], 0
        current.append(sentence)
        current_len += len(sentence) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def sections_from_markdown(text: str) -> list[tuple[str, str, None]]:
    """Split markdown/plain text on '# Heading' lines into (section, body, page=None)."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = "Introduction"
    current_body: list[str] = []
    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            if current_body:
                sections.append((current_title, current_body))
            current_title = match.group(1).strip()
            current_body = []
        else:
            current_body.append(line)
    if current_body:
        sections.append((current_title, current_body))
    return [(title, "\n".join(body).strip(), None) for title, body in sections if "\n".join(body).strip()]


def sections_from_docx(path: Path) -> list[tuple[str, str, None]]:
    doc = DocxDocument(str(path))
    sections: list[tuple[str, list[str]]] = []
    current_title = "Introduction"
    current_body: list[str] = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name.lower().startswith("heading"):
            if current_body:
                sections.append((current_title, current_body))
            current_title = text
            current_body = []
        else:
            current_body.append(text)
    if current_body:
        sections.append((current_title, current_body))
    return [(title, "\n".join(body).strip(), None) for title, body in sections if "\n".join(body).strip()]


def sections_from_pdf(path: Path) -> list[tuple[str, str, int]]:
    sections: list[tuple[str, str, int]] = []
    with fitz.open(str(path)) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            text = page.get_text().strip()
            if not text:
                continue
            first_line = text.splitlines()[0].strip()[:80] or f"Page {page_index}"
            sections.append((first_line, text, page_index))
    return sections


def parse_document(path: Path) -> list[tuple[str, str, int | None]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return sections_from_pdf(path)
    if suffix == ".docx":
        return sections_from_docx(path)
    if suffix in (".md", ".txt"):
        return sections_from_markdown(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported corpus file type: {path}")


def make_chunk_id(doc_id: str, section: str, text: str) -> str:
    digest = hashlib.sha256(f"{doc_id}::{section}::{text}".encode("utf-8")).hexdigest()
    return digest[:16]


def build_chunks(corpus_dir: Path) -> list[dict]:
    records: list[dict] = []
    paths = sorted(
        p for p in corpus_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".md", ".txt")
    )
    for path in paths:
        doc_id = path.stem
        for section, body, page in parse_document(path):
            for chunk_text in chunk_sentences(split_sentences(body)):
                records.append({
                    "chunk_id": make_chunk_id(doc_id, section, chunk_text),
                    "doc_id": doc_id,
                    "section": section,
                    "page": page,
                    "text": chunk_text,
                })
    return records


def build_dense_index(records: list[dict], model_name: str) -> "np.ndarray":
    model = SentenceTransformer(model_name)
    texts = [r["text"] for r in records]
    embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return embeddings.astype("float32")


def main() -> None:
    corpus_dir = Path(settings.corpus_dir)
    data_dir = Path(settings.data_dir)
    indexes_dir = Path(settings.indexes_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)

    records = build_chunks(corpus_dir)
    if not records:
        print(f"No corpus files found in {corpus_dir} -- nothing to ingest.")
        return

    chunk_ids = [r["chunk_id"] for r in records]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise RuntimeError("Duplicate chunk_id detected -- chunking is not content-unique.")

    chunks_path = Path(settings.chunks_path)
    with chunks_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    import faiss

    embeddings = build_dense_index(records, settings.embedding_model_name)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    faiss.write_index(index, settings.faiss_index_path)

    bm25 = build_bm25([r["text"] for r in records])
    import pickle

    with open(settings.bm25_index_path, "wb") as f:
        pickle.dump({"bm25": bm25, "chunk_ids": chunk_ids}, f)

    n_docs = len({r["doc_id"] for r in records})
    print(f"Ingested {len(records)} chunks from {n_docs} corpus documents.")
    print(f"chunks -> {chunks_path}")
    print(f"faiss index -> {settings.faiss_index_path} ({embeddings.shape[0]} vectors, dim={embeddings.shape[1]})")
    print(f"bm25 index -> {settings.bm25_index_path}")


if __name__ == "__main__":
    main()
