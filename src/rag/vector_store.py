"""
向量存储 — 基于 ChromaDB
对SOP文档块做嵌入索引，支持语义检索
"""

import os
from pathlib import Path
from typing import List, Optional

# ChromaDB 跨平台兼容：Windows 需要 sqlite3 3.35+，Linux 需要关闭 Rust 后端
os.environ.setdefault("CHROMA_SQLITE_VERSION", "3")
os.environ.setdefault("CHROMA_SEGMENT_PRODUCER_IMPL", "chromadb.segment.impl.vector.local_persistent_hnsw")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.config import Settings

from .document_loader import DocumentChunk


class VectorStore:
    """ChromaDB 向量存储封装"""

    COLLECTION_NAME = "lab_sop_docs"

    def __init__(self, persist_dir: str = None):
        if persist_dir is None:
            persist_dir = str(Path(__file__).parent.parent.parent / "chroma_db")

        Path(persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._ensure_collection()

    def _ensure_collection(self):
        """获取或创建集合"""
        try:
            self.collection = self.client.get_collection(self.COLLECTION_NAME)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"description": "实验室仪器SOP文档知识库"},
            )

    def index_chunks(self, chunks: List[DocumentChunk]):
        """将文档块索引入向量库（增量添加）"""
        existing_ids = set(self.collection.get()["ids"])

        ids_to_add = []
        docs_to_add = []
        metas_to_add = []

        for chunk in chunks:
            if chunk.chunk_id not in existing_ids:
                ids_to_add.append(chunk.chunk_id)
                docs_to_add.append(chunk.content)
                metas_to_add.append({
                    "source_file": chunk.source_file,
                    "section_title": chunk.section_title,
                    "chunk_index": chunk.chunk_index,
                })

        if ids_to_add:
            self.collection.add(
                ids=ids_to_add,
                documents=docs_to_add,
                metadatas=metas_to_add,
            )
            print(f"[OK] Vector store indexed {len(ids_to_add)} new chunks")
        else:
            print("[OK] Vector store is up to date")

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        """
        语义检索：给定查询文本，返回最相关的文档块

        Returns:
            [{content, source_file, section_title, distance}, ...]
        """
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        formatted = []
        for i in range(len(results["ids"][0])):
            formatted.append({
                "chunk_id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "source_file": results["metadatas"][0][i].get("source_file", ""),
                "section_title": results["metadatas"][0][i].get("section_title", ""),
                "distance": round(results["distances"][0][i], 4),
            })

        return formatted

    def get_collection_stats(self) -> dict:
        """获取向量库统计信息"""
        return {
            "collection_name": self.COLLECTION_NAME,
            "total_chunks": self.collection.count(),
        }
