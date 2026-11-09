from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
SIDE = obj({'requirement': TEXT, 'applicability': {'type': 'string', 'enum': ['required', 'not_applicable', 'unknown']}, 'harness_status': {'type': 'string', 'enum': ['sat', 'unsat', 'unknown', 'not_applicable']}, 'reason': TEXT, 'source_evidence': QUOTES})
CLAIM = obj({'claim_id': TEXT, 'necessary': {'type': 'string', 'enum': ['yes', 'no', 'unknown']}, 'necessity_reason': TEXT, 'before': SIDE, 'after': SIDE, 'same_blocker': {'type': 'string', 'enum': ['yes', 'no', 'unknown', 'not_applicable']}, 'harness_evidence': QUOTES, 'comparison_reason': TEXT, 'missing_information': arr(TEXT)})
ATTRIBUTION_SCHEMA = obj({'summary': TEXT, 'claims': arr(CLAIM)})
