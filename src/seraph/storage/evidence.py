from __future__ import annotations
from .sqlite import SQLiteWorldStore
class EvidenceStore:
    def __init__(self,path):self.path=path
