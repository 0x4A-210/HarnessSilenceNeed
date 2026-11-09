import re

from scheme_v8.llm.attribution import head, pipeline, policy
from scheme_v8.llm.attribution.spec import CLAUSES, PROTOCOL
from scheme_v8.llm.obligation_ledger import FACT_PROMPT, REGISTRY_PROMPT


PROMPTS = {
    "maintenance": head.MAINT_PROMPT + head.BATCH_RULES + policy.POLICY + policy.ledger_rules(False),
    "temporal": head.TIME_PROMPT + head.BATCH_RULES + policy.POLICY + policy.ledger_rules(True),
    "gate": policy.GATE_PROMPT,
    "fact": FACT_PROMPT,
    "registry": REGISTRY_PROMPT,
    "repair": head.REPAIR_PROMPT,
}

# Sample-derived wording removed in the rule audit (docs/规则审计.md).
REMOVED = re.compile(
    r"chunk partition|resumable|default-off|allocation|regression string|overloaded operator"
    r"|deprecat|absent setter|fixture may|root-directory|generated archive|scheduling"
    r"|arbitrary bytes|successor API|repeated call|constructors/destructors",
    re.I,
)


def test_prompts_have_no_sample_specific_rules():
    for name, text in PROMPTS.items():
        assert not REMOVED.search(text), name


def test_every_cited_clause_exists():
    known = set(CLAUSES) | set(PROTOCOL)
    for name, text in PROMPTS.items():
        for ref in re.findall(r"\b([DJTE]\d)[a-e]?\b", text):
            assert ref in known, (name, ref)


def test_specification_is_shared_by_judgement_calls():
    for name in ("maintenance", "temporal", "gate"):
        assert policy.POLICY in PROMPTS[name], name
