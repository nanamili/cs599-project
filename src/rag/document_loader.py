"""
SOP 文档加载器
从 config/sop_docs/ 加载 Markdown 文档，分割为可检索的文本块
"""

from pathlib import Path
from typing import List
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    """文档块"""
    chunk_id: str
    content: str
    source_file: str
    section_title: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)


def load_sop_documents(sop_dir: str = None) -> List[DocumentChunk]:
    """
    加载 config/sop_docs/ 下的所有 SOP 文档，
    按 ## 标题分割为独立文本块。
    """
    if sop_dir is None:
        sop_dir = Path(__file__).parent.parent.parent / "config" / "sop_docs"

    sop_dir = Path(sop_dir)
    if not sop_dir.exists():
        raise FileNotFoundError(f"SOP文档目录不存在: {sop_dir}")

    all_chunks = []

    for md_file in sorted(sop_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        chunks = _split_by_headers(content, md_file.name)
        all_chunks.extend(chunks)

    print(f"[OK] Loaded {len(all_chunks)} chunks from {len(list(sop_dir.glob('*.md')))} SOP files")
    return all_chunks


def _split_by_headers(content: str, filename: str) -> List[DocumentChunk]:
    """按 Markdown 标题分割文档"""
    chunks = []
    lines = content.split("\n")
    current_title = "概述"
    current_lines = []
    chunk_index = 0

    for line in lines:
        # 二级标题作为分块边界
        if line.startswith("## ") and len(current_lines) > 0:
            text = "\n".join(current_lines).strip()
            if len(text) > 50:  # 过滤太短的块
                chunk_id = f"{filename.replace('.md', '')}_{chunk_index}"
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    content=text,
                    source_file=filename,
                    section_title=current_title,
                    chunk_index=chunk_index,
                    metadata={"source": filename, "section": current_title},
                ))
                chunk_index += 1
            current_title = line.replace("## ", "").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    # 最后一个块
    if current_lines:
        text = "\n".join(current_lines).strip()
        if len(text) > 50:
            chunk_id = f"{filename.replace('.md', '')}_{chunk_index}"
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                content=text,
                source_file=filename,
                section_title=current_title,
                chunk_index=chunk_index,
                metadata={"source": filename, "section": current_title},
            ))

    return chunks
