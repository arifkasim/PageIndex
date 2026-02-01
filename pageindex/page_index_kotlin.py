import re
import os

def extract_nodes_from_kotlin(code_content: str, lines: list) -> list:
    """
    Parse Kotlin code using regex to extract classes, interfaces, objects, and functions.
    Uses brace counting to determine scope and nesting.
    """
    nodes = []
    
    # Regex patterns
    # Matches: class Foo, data class Foo, enum class Foo, interface Foo, object Foo
    # Group 2 is the keyword(s), Group 3 is the name
    class_pattern = re.compile(r'^\s*(private|public|protected|internal)?\s*(open|data|sealed|annotation|inner)?\s*(class|interface|object|enum\s+class)\s+([a-zA-Z0-9_]+)')
    
    # Matches: fun foo
    # Group 3 is the name
    fun_pattern = re.compile(r'^\s*(private|public|protected|internal|override|suspend|abstract|open|inline)*\s*fun\s+([a-zA-Z0-9_`]+)')

    # Matches: import foo.bar
    import_pattern = re.compile(r'^\s*import\s+')

    # Stack to track current parent node and its indentation/brace depth
    # Each item: {'node': dict, 'brace_count': int}
    stack = []
    
    # Track brace balance to identify when a node ends
    current_brace_balance = 0
    
    # Import tracking
    import_start_line = None
    import_end_line = None

    # Helper to clean text for brace counting (remove strings and comments)
    def count_braces(line):
        # Remove single line comments
        line = re.sub(r'//.*', '', line)
        # Remove strings (simple approximation, doesn't handle escaped quotes inside perfectly)
        line = re.sub(r'".*?"', '""', line)
        line = re.sub(r"'.*?'", "''", line)
        return line.count('{') - line.count('}')

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped_line = line.strip()
        
        # Check for import
        if import_pattern.match(stripped_line):
            if import_start_line is None:
                import_start_line = line_num
            import_end_line = line_num
            continue # Imports don't have body braces to track usually
        elif stripped_line and not stripped_line.startswith('//') and not stripped_line.startswith('package'):
            # Found non-import code (and not package decl which we ignore/treat as spacer)
            # If we have pending imports, flush them
            if import_start_line is not None:
                 nodes.append({
                    'title': 'Imports',
                    'type': 'imports',
                    'start_line': import_start_line,
                    'end_line': import_end_line,
                    'nodes': []
                 })
                 import_start_line = None
                 import_end_line = None
        
        # If we are just whitespace or package, we carry on keeping import_start_line active if set?
        # Actually if we have empty lines between imports, we might want to keep the block open.
        # But if we have 'package', that breaks import block? Usually package is before imports.
        # If we have 'package' after imports (weird), it breaks.
        # Let's assume empty lines extend the block if imports continue. 
        # But if imports end and we hit class, we flush.
        
        # Brace counting update
        balance_change = count_braces(line)
        current_brace_balance += balance_change
        
        # Check for node endings
        # If stack is not empty, check if current balance has dropped below the start balance of the top node
        while stack:
            top = stack[-1]
            # If we drop back to the level where the node started (or below), it's closed.
            # However, usually a node starts with '{' on the same line or next.
            # Let's assume standard formatting where '{' increases balance.
            # A node starting at balance N is closed when balance returns to N.
            if current_brace_balance <= top['start_balance']:
                # Node ended
                top['node']['end_line'] = line_num
                stack.pop()
            else:
                break

        # Check for new definitions
        # Only check if strictly code (not inside a multi-line comment, but we simplified that)
        
        match_class = class_pattern.search(line)
        match_fun = fun_pattern.search(line)
        
        new_node = None
        
        if match_class:
            # It's a class-like structure
            kind_modifiers = match_class.group(2)
            kind_type = match_class.group(3)
            name = match_class.group(4)
            
            node_type = 'class'
            if 'interface' in kind_type:
                node_type = 'interface'
            elif 'enum' in kind_type:
                node_type = 'enum'
            elif 'object' in kind_type:
                node_type = 'object'
            
            full_title = f"{kind_modifiers + ' ' + kind_type if kind_modifiers else kind_type} {name}"
            # Clean up extra spaces
            full_title = ' '.join(full_title.split()) 
            
            new_node = {
                'title': name,
                'type': node_type,
                'start_line': line_num,
                'end_line': line_num, # Interim
                'nodes': []
            }
            
        elif match_fun:
            name = match_fun.group(2)
            # Basic signature extraction - take line until end or '{'
            signature = line.split('{')[0].strip()
            if signature.endswith('='): 
                signature = signature[:-1].strip() # Handle single-expression functions
            
            new_node = {
                'title': f"{name}()",
                'type': 'function', # Default, check parent
                'start_line': line_num,
                'end_line': line_num,
                'signature': signature,
                'nodes': []
            }
            
            # Identify if method
            if stack and stack[-1]['node']['type'] in ['class', 'interface', 'object', 'enum']:
                 new_node['type'] = 'method'

        if new_node:
            # Add to parent or root
            if stack:
                stack[-1]['node']['nodes'].append(new_node)
            else:
                nodes.append(new_node)
            
            # Push to stack to track scope
            # We record the balance BEFORE this line (effectively) or currently? 
            # If the line has '{', the balance increased. We want to pop when it goes BACK to PRE-increase level.
            # So start_balance should be: brace_balance - balance_change (if change > 0 due to open brace)
            # Actually simpler: if line has '{', we expect balance to drop back to (current - 1) to close THIS brace.
            # But line might have multiple braces.
            # Let's say we are at depth D. We start a node. We expect to end when we go back to D.
            # Current brace balance includes the net change of this line.
            # If the class definition line has the opening '{', current balance is D+1. We return to D to close.
            # If it doesn't (next line), current is D. Next line makes it D+1.
            # We need to track the "baseline" balance for this node.
            
            # Robust approach: The node exists in the scope of the *previous* balance.
            # But if the line contains '{', the node content is inside the *new* balance.
            
            # Heuristic: The node closes when balance drops equal to the balance BEFORE the opening brace was added.
            # If line has '{', start_balance = current_brace_balance - 1 (roughly).
            
            start_balance = current_brace_balance - (1 if '{' in line else 0)
            stack.append({
                'node': new_node,
                'start_balance': start_balance
            })
            
    # Flush imports if file ends with them
    if import_start_line is not None:
         nodes.append({
            'title': 'Imports',
            'type': 'imports',
            'start_line': import_start_line,
            'end_line': import_end_line,
            'nodes': []
         })

    return nodes

def extract_node_text_content(nodes: list, lines: list) -> list:
    """Add source code text to each node based on line ranges."""
    def add_text_to_node(node):
        start = node['start_line'] - 1  # Convert to 0-indexed
        end = node['end_line']
        end = min(end, len(lines))
        node['text'] = '\n'.join(lines[start:end])

        # Recursively process children
        for child in node.get('nodes', []):
            add_text_to_node(child)

    for node in nodes:
        add_text_to_node(node)

    return nodes

def build_kotlin_file_tree(file_path: str, model: str = None) -> dict:
    """Build tree structure for a single Kotlin file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
    except (IOError, UnicodeDecodeError):
        return None

    lines = code_content.split('\n')

    # Extract nodes from the Kotlin file
    nodes = extract_nodes_from_kotlin(code_content, lines)

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
