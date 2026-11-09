from __future__ import annotations
from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
DECISION_SCHEMA = obj({'decision': {'type': 'string', 'enum': ['keep', 'dismiss', 'uncertain']}, 'reason': TEXT, 'source_evidence': QUOTES, 'harness_evidence': QUOTES, 'missing_information': arr(TEXT)})
