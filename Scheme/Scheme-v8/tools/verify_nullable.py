"""Check that a CLI backend accepts an output schema whose sections are
`anyOf: [object, null]`, and that the model fills exactly the requested one.

Usage: python tools/verify_nullable.py <provider> <model> <out_dir>
"""
import json
import sys
from pathlib import Path

from scheme_v8.budget import Budget
from scheme_v8.llm.backends import make_client
from scheme_v8.util import write_json

provider, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
client = make_client({'provider': provider, 'model': model, 'reasoning_effort': 'low', 'timeout_seconds': 600},
                     Budget({'seconds': 1800, 'max_llm_calls': 10, 'max_llm_input_tokens': 1_000_000}))
section = lambda props: {'anyOf': [{'type': 'object', 'properties': props, 'required': list(props),
                                    'additionalProperties': False}, {'type': 'null'}]}
schema = {'type': 'object', 'additionalProperties': False, 'required': ['turn', 'alpha', 'beta'],
          'properties': {'turn': {'type': 'string', 'enum': ['alpha', 'beta']},
                         'alpha': section({'items': {'type': 'array', 'items': {'type': 'string'}}}),
                         'beta': section({'value': {'type': 'integer'}})}}
results = []
for name, prompt in (('alpha', 'Set turn="alpha". Fill "alpha" with items ["x","y","z"]; set "beta" to null.'),
                     ('beta', 'Set turn="beta". Fill "beta" with value 7; set "alpha" to null.')):
    try:
        data = client.infer(prompt, schema, out / name)
        other = 'beta' if name == 'alpha' else 'alpha'
        results.append({'turn': name, 'ok': data['turn'] == name and isinstance(data[name], dict) and data[other] is None,
                        'response': data})
    except Exception as exc:
        results.append({'turn': name, 'ok': False, 'error': str(exc)[:500]})
write_json(out / 'summary.json', results)
print(json.dumps(results, ensure_ascii=False, indent=1))
client.close()
