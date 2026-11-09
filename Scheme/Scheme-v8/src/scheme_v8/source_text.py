def source_lines(value: str, keepends=False):
    if not value:
        return []
    parts = value.split('\n')
    terminated = value.endswith('\n')
    if terminated:
        parts.pop()
    if keepends:
        return [part + ('\n' if i < len(parts) - 1 or terminated else '') for i, part in enumerate(parts)]
    return [part.removesuffix('\r') for part in parts]
