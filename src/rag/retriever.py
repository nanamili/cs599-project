"""
检索器 — RAG检索的顶层接口
整合文档加载 + 向量存储 + 检索
"""

from typing import List, Optional
from .document_loader import load_sop_documents
from .vector_store import VectorStore


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取向量存储单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def init_knowledge_base(force_reload: bool = False):
    """初始化知识库：加载SOP文档并建立索引"""
    store = get_vector_store()

    if not force_reload and store.collection.count() > 0:
        print(f"[OK] Knowledge base ready ({store.collection.count()} chunks)")
        return store

    print("正在加载SOP文档...")
    chunks = load_sop_documents()

    print("正在建立向量索引（首次运行可能需要下载 embedding 模型）...")
    store.index_chunks(chunks)

    print(f"[OK] Knowledge base init complete: {len(chunks)} chunks indexed")
    return store


def search_sop(query: str, top_k: int = 3) -> List[dict]:
    """
    在SOP知识库中检索相关内容

    Args:
        query: 自然语言查询，如 "电镜样品怎么制备？"
        top_k: 返回最相关的K个结果

    Returns:
        相关文档块列表
    """
    store = get_vector_store()
    if store.collection.count() == 0:
        init_knowledge_base()

    results = store.search(query, top_k=top_k)

    if not results:
        return [{
            "content": "未找到相关SOP文档。请确认查询关键词或联系管理员。",
            "source_file": "N/A",
            "section_title": "无结果",
            "distance": 1.0,
        }]

    return results
