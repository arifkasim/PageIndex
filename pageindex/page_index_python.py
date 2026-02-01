import ast
import os
from typing import Optional

def extract_signature(node: ast.FunctionDef) -> str:
    """Extract function signature from AST node."""
    args = node.args
    parts = []

    # Handle positional-only args (Python 3.8+)
    if hasattr(args, 'posonlyargs'):
        for arg in args.posonlyargs:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f': {ast.unparse(arg.annotation)}'
            parts.append(arg_str)
        if args.posonlyargs:
            parts.append('/')

    # Calculate defaults offset
    num_args = len(args.args)
    num_defaults = len(args.defaults)
    defaults_offset = num_args - num_defaults

    # Handle regular args
    for i, arg in enumerate(args.args):
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f': {ast.unparse(arg.annotation)}'
        # Check if this arg has a default value
        default_idx = i - defaults_offset
        if default_idx >= 0 and default_idx < len(args.defaults):
            default_val = ast.unparse(args.defaults[default_idx])
            arg_str += f' = {default_val}'
        parts.append(arg_str)

    # Handle *args
    if args.vararg:
        vararg_str = f'*{args.vararg.arg}'
        if args.vararg.annotation:
            vararg_str += f': {ast.unparse(args.vararg.annotation)}'
        parts.append(vararg_str)
    elif args.kwonlyargs:
        parts.append('*')

    # Handle keyword-only args
    for i, arg in enumerate(args.kwonlyargs):
        arg_str = arg.arg
        if arg.annotation:
            arg_str += f': {ast.unparse(arg.annotation)}'
        if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
            arg_str += f' = {ast.unparse(args.kw_defaults[i])}'
        parts.append(arg_str)

    # Handle **kwargs
    if args.kwarg:
        kwarg_str = f'**{args.kwarg.arg}'
        if args.kwarg.annotation:
            kwarg_str += f': {ast.unparse(args.kwarg.annotation)}'
        parts.append(kwarg_str)

    # Build signature
    func_keyword = 'async def' if isinstance(node, ast.AsyncFunctionDef) else 'def'
    signature = f'{func_keyword} {node.name}({", ".join(parts)})'

    # Add return annotation
    if node.returns:
        signature += f' -> {ast.unparse(node.returns)}'

    return signature


def extract_docstring(node) -> Optional[str]:
    """Extract docstring from a class or function node."""
    if (node.body and
        isinstance(node.body[0], ast.Expr) and
        isinstance(node.body[0].value, ast.Constant) and
        isinstance(node.body[0].value.value, str)):
        return node.body[0].value.value
    return None


def extract_decorators(node) -> list:
    """Extract decorator names from a node."""
    decorators = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            decorators.append(f'@{decorator.id}')
        elif isinstance(decorator, ast.Attribute):
            decorators.append(f'@{ast.unparse(decorator)}')
        elif isinstance(decorator, ast.Call):
            decorators.append(f'@{ast.unparse(decorator)}')
    return decorators


def extract_nodes_from_python(code_content: str, lines: list) -> list:
    """
    Parse Python AST and extract classes/functions with line ranges.
    Returns a flat list of nodes with hierarchy information.
    """
    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        return []

    nodes = []

    def process_node(ast_node, parent_type=None):
        """Recursively process AST nodes."""
        if isinstance(ast_node, ast.ClassDef):
            class_node = {
                'title': ast_node.name,
                'type': 'class',
                'start_line': ast_node.lineno,
                'end_line': ast_node.end_lineno,
                'docstring': extract_docstring(ast_node),
                'decorators': extract_decorators(ast_node),
                'nodes': []
            }

            # Process methods and nested classes
            for child in ast_node.body:
                child_nodes = process_node(child, parent_type='class')
                if child_nodes:
                    class_node['nodes'].extend(child_nodes if isinstance(child_nodes, list) else [child_nodes])

            return class_node

        elif isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Determine if this is a method or function
            if parent_type == 'class':
                node_type = 'method'
            else:
                node_type = 'function'

            func_node = {
                'title': f'{ast_node.name}()',
                'type': node_type,
                'start_line': ast_node.lineno,
                'end_line': ast_node.end_lineno,
                'signature': extract_signature(ast_node),
                'docstring': extract_docstring(ast_node),
                'decorators': extract_decorators(ast_node),
                'nodes': []
            }

            # Process nested functions/classes
            for child in ast_node.body:
                child_nodes = process_node(child, parent_type='function')
                if child_nodes:
                    func_node['nodes'].extend(child_nodes if isinstance(child_nodes, list) else [child_nodes])

            return func_node

        return None

    # Process top-level nodes
    current_imports = []
    
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            current_imports.append(node)
        else:
            # If we were collecting imports, save them now
            if current_imports:
                import_nodes = []
                for imp in current_imports:
                    import_nodes.append({
                        'title': ast.unparse(imp),
                        'type': 'import',
                        'start_line': imp.lineno,
                        'end_line': imp.end_lineno if hasattr(imp, 'end_lineno') else imp.lineno,
                        'nodes': []
                    })
                
                import_node = {
                    'title': 'Imports',
                    'type': 'imports',
                    'start_line': current_imports[0].lineno,
                    'end_line': current_imports[-1].end_lineno if hasattr(current_imports[-1], 'end_lineno') else current_imports[-1].lineno,
                    'nodes': import_nodes
                }
                nodes.append(import_node)
                current_imports = []
            
            result = process_node(node)
            if result:
                nodes.append(result)

    # Handle trailing imports (rare at top level context if file ends with imports)
    if current_imports:
        import_nodes = []
        for imp in current_imports:
            import_nodes.append({
                'title': ast.unparse(imp),
                'type': 'import',
                'start_line': imp.lineno,
                'end_line': imp.end_lineno if hasattr(imp, 'end_lineno') else imp.lineno,
                'nodes': []
            })
            
        import_node = {
            'title': 'Imports',
            'type': 'imports',
            'start_line': current_imports[0].lineno,
            'end_line': current_imports[-1].end_lineno if hasattr(current_imports[-1], 'end_lineno') else current_imports[-1].lineno,
            'nodes': import_nodes
        }
        nodes.append(import_node)

    return nodes


def extract_node_text_content(nodes: list, lines: list) -> list:
    """Add source code text to each node based on line ranges."""
    def add_text_to_node(node):
        start = node['start_line'] - 1  # Convert to 0-indexed
        end = node['end_line']
        node['text'] = '\n'.join(lines[start:end])

        # Recursively process children
        for child in node.get('nodes', []):
            add_text_to_node(child)

    for node in nodes:
        add_text_to_node(node)

    return nodes


def build_python_file_tree(file_path: str, model: str = None) -> dict:
    """Build tree structure for a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    lines = code_content.split('\n')

    # Extract nodes from the Python file
    nodes = extract_nodes_from_python(code_content, lines)

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
