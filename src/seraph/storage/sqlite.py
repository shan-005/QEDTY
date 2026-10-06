from __future__ import annotations
import json,sqlite3
from pathlib import Path
from seraph.ontology.entities import Entity
from seraph.ontology.relations import Relationship
class SQLiteWorldStore:
    def __init__(self,path:str|Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _conn(self):
        c=sqlite3.connect(self.path); c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA journal_mode=WAL"); return c
    def _init(self):
        with self._conn() as c:c.executescript("CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,payload TEXT NOT NULL);CREATE TABLE IF NOT EXISTS relationships(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,target_id TEXT NOT NULL,payload TEXT NOT NULL,FOREIGN KEY(source_id) REFERENCES entities(id),FOREIGN KEY(target_id) REFERENCES entities(id));CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);")
    def put_entity(self,e:Entity):
        p=json.dumps(e.model_dump(mode="json"),sort_keys=True,separators=(",",":"));
        with self._conn() as c:
            row=c.execute("SELECT payload FROM entities WHERE id=?",(e.entity_id,)).fetchone()
            if row and row[0]!=p:raise ValueError("entity collision")
            c.execute("INSERT OR IGNORE INTO entities(id,payload) VALUES (?,?)",(e.entity_id,p))
    def put_relationship(self,r:Relationship):
        p=json.dumps(r.model_dump(mode="json"),sort_keys=True,separators=(",",":"))
        with self._conn() as c:
            if c.execute("SELECT 1 FROM entities WHERE id=?",(r.source.entity_id,)).fetchone() is None:raise KeyError("source missing")
            if c.execute("SELECT 1 FROM entities WHERE id=?",(r.target.entity_id,)).fetchone() is None:raise KeyError("target missing")
            row=c.execute("SELECT payload FROM relationships WHERE id=?",(r.relationship_id,)).fetchone()
            if row and row[0]!=p:raise ValueError("relationship collision")
            c.execute("INSERT OR IGNORE INTO relationships(id,source_id,target_id,payload) VALUES (?,?,?,?)",(r.relationship_id,r.source.entity_id,r.target.entity_id,p))
