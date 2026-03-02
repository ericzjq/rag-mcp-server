"""
BM25Indexer（C11）：接收 SparseEncoder 的 term statistics，计算 IDF，构建倒排索引，持久化到 data/db/bm25/。
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.types import ChunkRecord

# BM25 常数（常用默认）
K1 = 1.2
B = 0.75


def _idf(n: int, df: int) -> float:
    """IDF(term) = log((N - df + 0.5) / (df + 0.5))。"""
    if df <= 0 or n < df:
        return 0.0
    return math.log((n - df + 0.5) / (df + 0.5))


class BM25Indexer:
    """构建并持久化 BM25 倒排索引；支持 load 与 query 返回稳定 top ids。"""

    def __init__(self, index_dir: str = "data/db/bm25") -> None:
        self._index_dir = Path(index_dir)
        self._n: int = 0
        self._avgdl: float = 0.0
        self._terms: Dict[str, Dict[str, Any]] = {}  # term -> {idf, postings: [{chunk_id, tf, doc_length}]}

    def build(self, records: List[ChunkRecord]) -> "BM25Indexer":
        """
        根据 ChunkRecord 列表（含 sparse_vector）计算 IDF，构建倒排索引。

        Args:
            records: SparseEncoder 输出，每项须有 sparse_vector: Dict[str, float]（term -> tf）。

        Returns:
            self，便于链式调用。
        """
        self._n = len(records)
        if self._n == 0:
            self._avgdl = 0.0
            self._terms = {}
            return self

        # 每个 chunk 的 doc_length = sum(sparse_vector.values())
        doc_lengths: List[float] = []
        term_to_df: Dict[str, int] = {}
        term_to_postings: Dict[str, List[Dict[str, Any]]] = {}

        for r in records:
            sv = r.sparse_vector or {}
            dl = sum(sv.values())
            doc_lengths.append(dl)
            for term, tf in sv.items():
                if term not in term_to_df:
                    term_to_df[term] = 0
                    term_to_postings[term] = []
                term_to_df[term] += 1
                term_to_postings[term].append({
                    "chunk_id": r.id,
                    "tf": float(tf),
                    "doc_length": dl,
                })

        self._avgdl = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0
        self._terms = {}
        for term, df in term_to_df.items():
            idf_val = _idf(self._n, df)
            self._terms[term] = {
                "idf": idf_val,
                "postings": term_to_postings[term],
            }
        return self

    def save(self, index_path: Optional[str] = None) -> Path:
        """序列化索引到 index_path 或 self._index_dir / index.json；创建目录。"""
        path = Path(index_path) if index_path else (self._index_dir / "index.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "N": self._n,
            "avgdl": self._avgdl,
            "terms": self._terms,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        return path

    def load(self, index_path: Optional[str] = None) -> "BM25Indexer":
        """从 index_path 或 self._index_dir / index.json 加载索引。"""
        path = Path(index_path) if index_path else (self._index_dir / "index.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._n = data["N"]
        self._avgdl = data["avgdl"]
        self._terms = data["terms"]
        return self

    def query(self, terms: List[str], top_k: int = 10) -> List[str]:
        """
        对给定 term 列表做 BM25 打分，返回得分最高的 top_k 个 chunk_id（稳定排序）。

        使用 BM25 公式：score += IDF(t) * (tf * (k1+1)) / (tf + k1 * (1 - b + b * dl/avgdl))
        """
        if not terms or self._n == 0:
            return []
        scores: Dict[str, float] = {}
        for term in terms:
            t = term.strip().lower()
            if not t or t not in self._terms:
                continue
            info = self._terms[t]
            idf = info["idf"]
            for p in info["postings"]:
                cid = p["chunk_id"]
                tf = p["tf"]
                dl = p["doc_length"]
                denom = tf + K1 * (1 - B + B * dl / self._avgdl) if self._avgdl > 0 else tf + K1
                score = idf * (tf * (K1 + 1)) / denom
                scores[cid] = scores.get(cid, 0.0) + score
        # 稳定排序：先按分降序，再按 chunk_id 升序
        sorted_ids = sorted(scores.keys(), key=lambda x: (-scores[x], x))
        return sorted_ids[:top_k]
