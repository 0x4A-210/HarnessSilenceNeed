from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from tree_sitter import Language
from tree_sitter import Parser
import tree_sitter_c
import tree_sitter_cpp
C = Language(tree_sitter_c.language())
CPP = Language(tree_sitter_cpp.language())

def walk(node):
    stack = [node]
    while stack:
        item = stack.pop()
        yield item
        stack.extend(reversed(item.named_children))

def text(node) -> str:
    return node.text.decode('utf-8', errors='replace') if node is not None else ''

def parents(node):
    while node is not None:
        yield node
        node = node.parent

def function_name(declarator):
    node = declarator.child_by_field_name('declarator')
    while node is not None and node.type in ('pointer_declarator', 'parenthesized_declarator'):
        node = node.child_by_field_name('declarator') or next(iter(node.named_children), None)
    return text(node) if node is not None and node.type in ('identifier', 'field_identifier') else None

@dataclass
class Function:
    name: str
    node: object
    declaration: object
    params: list[str]
    arity: int
    variadic: bool
    definition: bool

class Syntax:

    def __init__(self, reader):
        self.reader = reader
        self.trees = {}
        self.function_cache = {}

    def tree(self, path):
        if path not in self.trees:
            language = CPP if Path(path).suffix.lower() in ('.cc', '.cpp', '.cxx', '.hpp', '.hxx') else C
            self.trees[path] = Parser(language).parse(self.reader.index(path))
        return self.trees[path]

    def functions(self, path) -> list[Function]:
        self.reader.budget.check()
        if path in self.function_cache:
            return self.function_cache[path]
        result = []
        for node in walk(self.tree(path).root_node):
            if node.type != 'function_declarator' or node.has_error:
                continue
            name = function_name(node)
            if not name or any((p.type in ('parameter_declaration', 'optional_parameter_declaration') for p in parents(node.parent))):
                continue
            container = next((p for p in parents(node.parent) if p.type in ('function_definition', 'declaration')), None)
            if container is None:
                continue
            param_node = node.child_by_field_name('parameters')
            params, variadic = ([], False)
            for p in param_node.named_children if param_node else []:
                if p.type == 'variadic_parameter':
                    variadic = True
                elif text(p) != 'void':
                    decl = p.child_by_field_name('declarator')
                    ids = [n for n in walk(decl) if n.type == 'identifier'] if decl else []
                    params.append(text(ids[-1]) if ids else '')
            result.append(Function(name, container, node, params, len(params), variadic, container.type == 'function_definition'))
        self.function_cache[path] = result
        return result

    def calls(self, node):
        for n in walk(node):
            if n.type == 'call_expression':
                fn = n.child_by_field_name('function')
                args = n.child_by_field_name('arguments')
                if fn is not None and fn.type == 'identifier' and (args is not None):
                    yield (text(fn), list(args.named_children), n)

    def enclosing_function(self, path, line):
        found = [f for f in self.functions(path) if f.definition and f.node.start_point.row + 1 <= line <= f.node.end_point.row + 1]
        return min(found, key=lambda f: f.node.end_byte - f.node.start_byte) if found else None
