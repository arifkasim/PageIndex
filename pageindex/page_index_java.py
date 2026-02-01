import javalang
import os
from typing import Optional

try:
    from .utils import (
        count_tokens,
    )
except ImportError:
    from utils import (
        count_tokens,
    )

def extract_nodes_from_java(code_content: str, lines: list) -> list:
    """
    Parse Java AST and extract classes/interface/enum/methods with line ranges.
    Returns a flat list of nodes with hierarchy information.
    """
    try:
        tree = javalang.parse.parse(code_content)
    except (javalang.parser.JavaSyntaxError, IndexError, TypeError):
        return []

    nodes = []

    def get_line_range(node):
        # javalang doesn't provide precise end lines, so we estimate
        start_line = node.position.line if node.position else 1
        return start_line

    def process_node(ast_node, parent_type=None):
        """Recursively process AST nodes."""
        
        # Handle Class, Interface, Enum
        if isinstance(ast_node, (javalang.tree.ClassDeclaration, javalang.tree.InterfaceDeclaration, javalang.tree.EnumDeclaration)):
            node_type = 'class'
            if isinstance(ast_node, javalang.tree.InterfaceDeclaration):
                node_type = 'interface'
            elif isinstance(ast_node, javalang.tree.EnumDeclaration):
                node_type = 'enum'

            start_line = get_line_range(ast_node)
            # Estimate end line by looking at the next sibling or end of file
            # This is a limitation of javalang
            
            node_data = {
                'title': ast_node.name,
                'type': node_type,
                'start_line': start_line,
                'end_line': start_line, # Will be updated later
                'docstring': ast_node.documentation,
                'decorators': [a.name for a in ast_node.annotations] if hasattr(ast_node, 'annotations') else [],
                'nodes': []
            }

            # Process body
            if hasattr(ast_node, 'body'):
                for child in ast_node.body:
                    child_nodes = process_node(child, parent_type=node_type)
                    if child_nodes:
                        node_data['nodes'].extend(child_nodes if isinstance(child_nodes, list) else [child_nodes])
            
            # Helper to find the max end_line from children
            max_child_end = start_line
            for child in node_data['nodes']:
                if child['end_line'] > max_child_end:
                    max_child_end = child['end_line']
            node_data['end_line'] = max(start_line, max_child_end)
            
            # Simple heuristic: expand to match braces if possible, but without token stream it's hard.
            # We will rely on children to push the end_line down.
            
            return node_data

        # Handle Methods and Constructors
        elif isinstance(ast_node, (javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration)):
            node_type = 'method'
            name = ast_node.name
            
            # Build signature
            params = []
            if ast_node.parameters:
                for param in ast_node.parameters:
                    param_str = f"{param.type.name} {param.name}"
                    params.append(param_str)
            
            signature = f"{name}({', '.join(params)})"
            if isinstance(ast_node, javalang.tree.MethodDeclaration) and ast_node.return_type:
                signature = f"{ast_node.return_type.name} " + signature
            
            start_line = get_line_range(ast_node)
            
            node_data = {
                'title': f"{name}()",
                'type': node_type,
                'start_line': start_line,
                'end_line': start_line, # Will set based on body
                'signature': signature,
                'docstring': ast_node.documentation,
                'decorators': [a.name for a in ast_node.annotations] if hasattr(ast_node, 'annotations') else [],
                'nodes': []
            }
            
            # Estimate end line based on statement body
            if ast_node.body:
                last_stmt = ast_node.body[-1]
                if hasattr(last_stmt, 'position') and last_stmt.position:
                     node_data['end_line'] = last_stmt.position.line + 1
                else:
                    # Fallback if no position on last statement
                     node_data['end_line'] = start_line
            else:
                 node_data['end_line'] = start_line

            return node_data

        return None

    # Process Imports
    if tree.imports:
        first_import = tree.imports[0]
        last_import = tree.imports[-1]
        
        start_line = get_line_range(first_import)
        end_line = get_line_range(last_import)
        
        # Javalang position is start, we assume import is 1 line usually.
        # So end_line is at least that.
        
        node_data = {
            'title': 'Imports',
            'type': 'imports',
            'start_line': start_line,
            'end_line': end_line,
            'nodes': []
        }
        nodes.append(node_data)

    # Iterate over types in the compilation unit
    if tree.types:
        for t in tree.types:
            result = process_node(t)
            if result:
                nodes.append(result)

    return nodes

def extract_node_text_content(nodes: list, lines: list) -> list:
    """Add source code text to each node based on line ranges."""
    def add_text_to_node(node):
        start = node['start_line'] - 1  # Convert to 0-indexed
        end = node['end_line']
        # Ensure we don't go out of bounds
        end = min(end, len(lines))
        node['text'] = '\n'.join(lines[start:end])

        # Recursively process children
        for child in node.get('nodes', []):
            add_text_to_node(child)

    for node in nodes:
        add_text_to_node(node)

    return nodes

def build_java_file_tree(file_path: str, model: str = None) -> dict:
    """Build tree structure for a single Java file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    lines = code_content.split('\n')

    # Extract nodes from the Java file
    nodes = extract_nodes_from_java(code_content, lines)

    # Add text content to nodes
    nodes = extract_node_text_content(nodes, lines)

    file_node = {
        'title': os.path.basename(file_path),
        'type': 'file',
        'path': file_path,
        'start_line': 1,
        'end_line': len(lines),
        'text': code_content,
        'nodes': nodes
    }

    return file_node
