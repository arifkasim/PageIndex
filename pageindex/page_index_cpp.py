import os
import tree_sitter
try:
    import tree_sitter_c
    import tree_sitter_cpp
except ImportError:
    pass

def get_parser(lang_name):
    parser = tree_sitter.Parser()
    if lang_name == 'c':
        parser.language = tree_sitter.Language(tree_sitter_c.language())
    elif lang_name == 'cpp':
        parser.language = tree_sitter.Language(tree_sitter_cpp.language())
    return parser

def extract_nodes_from_cpp(code_content: str, lines: list, lang: str = 'cpp') -> list:
    """
    Parse C/C++ code using Tree-sitter.
    
    Args:
        lang: 'c' or 'cpp'
    """
    if lang not in ['c', 'cpp']:
        return []

    try:
        parser = get_parser(lang)
        tree = parser.parse(bytes(code_content, "utf8"))
    except Exception as e:
        print(f"Error parsing {lang} code: {e}")
        return []

    nodes = []

    def get_line_range(node):
        return node.start_point.row + 1, node.end_point.row + 1

    def process_node(ts_node, parent_type=None):
        """Recursively process Tree-sitter nodes."""
        
        node_type = ts_node.type
        
        # Mapping Tree-sitter types to our schema
        mapped_type = None
        title = None
        
        # C/C++ specific node types
        if node_type in ['function_definition', 'template_function']:
            mapped_type = 'function'
            # Extract name
            declarator = ts_node.child_by_field_name('declarator')
            if declarator:
                 title = declarator.text.decode('utf8') + "()"
            
            if parent_type in ['class', 'struct']:
                mapped_type = 'method'
        
        elif node_type in ['class_specifier', 'struct_specifier']:
            mapped_type = 'class'
            if node_type == 'struct_specifier':
                mapped_type = 'struct'
            
            name_node = ts_node.child_by_field_name('name')
            if name_node:
                title = name_node.text.decode('utf8')
            else:
                title = "<anonymous>"

        elif node_type == 'namespace_definition':
            mapped_type = 'namespace'
            name_node = ts_node.child_by_field_name('name')
            if name_node:
                title = name_node.text.decode('utf8')

        # If it's a node we care about
        if mapped_type:
            start_line, end_line = get_line_range(ts_node)
            
            # Helper to get signature or full text for signature
            # For now simplified
            signature = "" 
            
            node_data = {
                'title': title if title else mapped_type,
                'type': mapped_type,
                'start_line': start_line,
                'end_line': end_line,
                'nodes': []
            }

            # Recurse children
            # We need to iterate over named children
            for child in ts_node.children:
                child_nodes = process_node(child, parent_type=mapped_type)
                if child_nodes:
                     node_data['nodes'].extend(child_nodes if isinstance(child_nodes, list) else [child_nodes])
            
            return node_data
        
        # If not a mapped type, just recurse children and return their results (flattened)
        # e.g. a namespace contains classes, we want those classes.
        # But we only want to flatten if we didn't create a node for THIS ts_node.
        
        results = []
        for child in ts_node.children:
            child_result = process_node(child, parent_type)
            if child_result:
                if isinstance(child_result, list):
                    results.extend(child_result)
                else:
                    results.append(child_result)
        return results

    # Process root
    root_nodes = process_node(tree.root_node)
    if isinstance(root_nodes, dict):
        nodes.append(root_nodes)
    elif isinstance(root_nodes, list):
        nodes.extend(root_nodes)

    return nodes

def extract_node_text_content(nodes: list, lines: list) -> list:
    """Add source code text to each node based on line ranges."""
    def add_text_to_node(node):
        start = node['start_line'] - 1 
        end = node['end_line']
        end = min(end, len(lines))
        node['text'] = '\n'.join(lines[start:end])

        for child in node.get('nodes', []):
            add_text_to_node(child)

    for node in nodes:
        add_text_to_node(node)

    return nodes

def build_cpp_file_tree(file_path: str, model: str = None) -> dict:
    """Build tree structure for a single C/C++ file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    lines = code_content.split('\n')

    # Determine C or C++
    ext = os.path.splitext(file_path)[1].lower()
    lang = 'c' if ext in ['.c', '.h'] else 'cpp'

    # Extract nodes
    nodes = extract_nodes_from_cpp(code_content, lines, lang=lang)

    # Add text content
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
