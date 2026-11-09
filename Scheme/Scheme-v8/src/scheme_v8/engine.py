"""Select the analysis engine and model backend from the config."""
from .llm.backends import make_client


def analyze(input_root, output, config, client_factory=make_client):
    if config['llm']['engine'] == 'cascade_session':
        from .llm.attribution.cascade import analyze_cascade
        return analyze_cascade(input_root, output, config, client_factory)
    from .llm.attribution.pipeline import analyze_ledger
    return analyze_ledger(input_root, output, config, client_factory)


def protocol(config):
    if config['llm']['engine'] == 'cascade_session':
        from .llm.attribution.cascade import cascade_protocol_hashes
        return cascade_protocol_hashes(config)
    from .llm.attribution.pipeline import protocol_hashes
    return protocol_hashes(config)
