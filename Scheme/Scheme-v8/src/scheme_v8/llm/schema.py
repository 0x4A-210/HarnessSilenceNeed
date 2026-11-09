def obj(fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}

def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}

def arr(item):
    return {'type': 'array', 'items': item}
TEXT = {'type': 'string'}
BOOL = {'type': 'boolean'}
QUOTE = obj({'evidence_id': TEXT, 'quote': TEXT})
QUOTES = arr(QUOTE)

def validate_schema(value, schema, path='$'):
    """Small strict validator for the exact schema subset above, no coercion."""
    if 'anyOf' in schema:
        errors = []
        for option in schema['anyOf']:
            try:
                validate_schema(value, option, path)
                return
            except ValueError as exc:
                errors.append(str(exc))
        raise ValueError(f'{path}: matches no anyOf option ({"; ".join(errors)[:300]})')
    kind = schema['type']
    if kind == 'null':
        if value is not None:
            raise ValueError(f'{path}: expected null')
        return
    if kind == 'object':
        if not isinstance(value, dict):
            raise ValueError(f'{path}: expected object')
        if set(value) != set(schema['properties']):
            raise ValueError(f'{path}: missing or extra fields')
        for key, sub in schema['properties'].items():
            validate_schema(value[key], sub, path + '.' + key)
    elif kind == 'array':
        if not isinstance(value, list):
            raise ValueError(f'{path}: expected array')
        for i, item in enumerate(value):
            validate_schema(item, schema['items'], f'{path}[{i}]')
    elif kind == 'boolean':
        if type(value) is not bool:
            raise ValueError(f'{path}: expected boolean')
    elif kind == 'integer':
        if type(value) is not int:
            raise ValueError(f'{path}: expected integer')
    elif kind == 'string':
        if not isinstance(value, str):
            raise ValueError(f'{path}: expected string')
        if 'enum' in schema and value not in schema['enum']:
            raise ValueError(f'{path}: invalid enum')
