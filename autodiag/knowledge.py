"""Small, dependency-free SQLite FTS5 knowledge base."""
from __future__ import annotations
import hashlib, re, sqlite3
from pathlib import Path

class KnowledgeStore:
    def __init__(self, path="~/.autodiag/kb.sqlite"):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript("""CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY,title TEXT,source TEXT UNIQUE,content_hash TEXT);
        CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document_id INTEGER,title TEXT,page INTEGER,text TEXT,content_hash TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(id UNINDEXED,title,text);""")
        self.db.commit()
    def ingest(self, paths):
        added = 0
        for path in map(Path, paths):
            raw = path.read_text(errors="replace")
            digest = hashlib.sha256(raw.encode()).hexdigest()
            if self.db.execute("SELECT 1 FROM documents WHERE source=? AND content_hash=?", (str(path), digest)).fetchone(): continue
            old = self.db.execute("SELECT id FROM documents WHERE source=?", (str(path),)).fetchone()
            if old:
                old_chunks = [row[0] for row in self.db.execute("SELECT id FROM chunks WHERE document_id=?", (old[0],))]
                for chunk_id in old_chunks:
                    self.db.execute("DELETE FROM chunks_fts WHERE id=?", (chunk_id,))
                self.db.execute("DELETE FROM chunks WHERE document_id=?", (old[0],))
                self.db.execute("DELETE FROM documents WHERE id=?", (old[0],))
            cur = self.db.execute("INSERT OR REPLACE INTO documents(title,source,content_hash) VALUES(?,?,?)", (path.stem, str(path), digest))
            docid = cur.lastrowid
            parts = re.split(r"(?m)^#{1,3}\s+", raw)
            for i, text in enumerate(parts):
                text = text.strip()
                if not text: continue
                cid = "c" + hashlib.sha256(f"{digest}:{i}".encode()).hexdigest()[:12]
                self.db.execute("INSERT OR REPLACE INTO chunks VALUES(?,?,?,?,?,?)", (cid, docid, path.stem, i + 1, text, digest))
                self.db.execute("INSERT OR REPLACE INTO chunks_fts(id,title,text) VALUES(?,?,?)", (cid, path.stem, text)); added += 1
        self.db.commit(); return added
    def search(self, query, limit=12):
        q = " ".join(re.findall(r"[A-Za-z0-9_]+", query))
        if not q: return []
        terms = q.split()
        match = " OR ".join(terms)
        rows = self.db.execute(
            "SELECT c.id,c.title,c.page,c.text FROM chunks_fts f "
            "JOIN chunks c ON c.id=f.id WHERE chunks_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (match, limit),
        ).fetchall()
        return [{"handle": r[0], "title": r[1], "page": r[2], "text": r[3]} for r in rows]
