import os
import asyncio
from typing import Optional
try:
    from .utils import (
        count_tokens,
        write_node_id,
        format_structure,
        generate_node_summary,
        structure_to_list,
        create_clean_structure_for_description,
        generate_doc_description,
        ChatGPT_API_async
    )
except ImportError:
    from utils import (
        count_tokens,
        write_node_id,
        format_structure,
        generate_node_summary,
        structure_to_list,
        create_clean_structure_for_description,
        generate_doc_description,
        generate_doc_description,
        ChatGPT_API_async
    )

try:
    from .page_index_java import build_java_file_tree
except ImportError:
    from pageindex.page_index_java import build_java_file_tree

try:
    from .page_index_kotlin import build_kotlin_file_tree
except ImportError:
    from pageindex.page_index_kotlin import build_kotlin_file_tree

try:
    from .page_index_cpp import build_cpp_file_tree
except ImportError:
    from pageindex.page_index_cpp import build_cpp_file_tree

try:
    from .page_index_python import build_python_file_tree
except ImportError:
    from pageindex.page_index_python import build_python_file_tree


def get_python_files(directory: str) -> list:
    """Recursively find all .py files in a directory."""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and common non-source directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env']]
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return sorted(python_files)





def build_file_tree(file_path: str, model: str = None) -> dict:
    """Build tree structure for a single Python or Java file."""
    if file_path.endswith('.java'):
        return build_java_file_tree(file_path, model)
    elif file_path.endswith('.kt'):
        return build_kotlin_file_tree(file_path, model)
    elif file_path.endswith(('.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
        return build_cpp_file_tree(file_path, model)
    elif file_path.endswith('.py'):
        return build_python_file_tree(file_path, model)
    
    return None


def build_directory_tree(dir_path: str, model: str = None) -> dict:
    """
    Recursively process directory and build unified tree.
    Returns a tree structure with directories containing files and code nodes (Python/Java).
    """
    dir_name = os.path.basename(os.path.normpath(dir_path))

    dir_node = {
        'title': dir_name,
        'type': 'directory',
        'path': dir_path,
        'nodes': []
    }

    # Get all items in directory
    try:
        items = sorted(os.listdir(dir_path))
    except PermissionError:
        return dir_node

    # Process subdirectories and files
    subdirs = []
    files = []

    for item in items:
        item_path = os.path.join(dir_path, item)

        # Skip hidden files/directories and common non-source directories
        if item.startswith('.') or item in ['__pycache__', 'node_modules', 'venv', '.venv', 'env', '.env', '.git', 'target', 'build', 'out']:
            continue

        if os.path.isdir(item_path):
            subdirs.append(item_path)
        elif item.endswith(('.py', '.java', '.kt', '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
            files.append(item_path)

    # Add subdirectories first
    for subdir_path in subdirs:
        subdir_node = build_directory_tree(subdir_path, model)
        # Only add if the directory contains code files (directly or nested)
        if subdir_node and has_code_content(subdir_node):
            dir_node['nodes'].append(subdir_node)

    # Add code files
    for file_path in files:
        file_node = build_file_tree(file_path, model)
        if file_node:
            dir_node['nodes'].append(file_node)

    return dir_node


def has_code_content(node: dict) -> bool:
    """Check if a directory node contains any code files (directly or nested)."""
    if node.get('type') == 'file':
        return True

    for child in node.get('nodes', []):
        if has_code_content(child):
            return True

    return False


def clean_empty_nodes(node: dict) -> dict:
    """Remove empty 'nodes' lists from the tree."""
    if 'nodes' in node:
        # Recursively clean children
        node['nodes'] = [clean_empty_nodes(child) for child in node['nodes']]
        # Remove if empty
        if not node['nodes']:
            del node['nodes']
    return node


def tree_thinning_for_code(structure: dict, min_token_threshold: int, model: str) -> dict:
    """
    Apply tree thinning to merge small code nodes.
    Similar to markdown thinning but for code structures.
    """
    def get_node_tokens(node: dict) -> int:
        """Calculate total tokens for a node including children."""
        text = node.get('text', '')
        total = count_tokens(text, model=model) if text else 0
        for child in node.get('nodes', []):
            total += get_node_tokens(child)
        return total

    def thin_node(node: dict) -> dict:
        """Apply thinning to a single node."""
        if 'nodes' not in node or not node['nodes']:
            return node

        # First, recursively thin children
        node['nodes'] = [thin_node(child) for child in node['nodes']]

        # Check if this node's total tokens is below threshold
        total_tokens = get_node_tokens(node)

        if total_tokens < min_token_threshold and node.get('type') in ['class', 'function', 'method']:
            # Merge children into parent
            merged_text = node.get('text', '')
            for child in node.get('nodes', []):
                child_text = child.get('text', '')
                if child_text:
                    if merged_text and not merged_text.endswith('\n'):
                        merged_text += '\n'
                    merged_text += child_text

            node['text'] = merged_text
            del node['nodes']

        return node

    return thin_node(structure)


async def get_code_node_summary(node: dict, summary_token_threshold: int, model: str) -> str:
    """Generate summary for a code node."""
    node_text = node.get('text', '')
    signature = node.get('signature', '')
    docstring = node.get('docstring', '')
    node_type = node.get('type', '')

    # If the node is small enough, return the docstring or a simple description
    num_tokens = count_tokens(node_text, model=model)
    if num_tokens < summary_token_threshold:
        if docstring:
            return docstring.strip().split('\n')[0]  # First line of docstring
        return node_text[:200] if node_text else ''

    # For larger nodes, generate a summary using LLM
    prompt = f"""You are given a Python {node_type}. Generate a concise one-sentence summary of what it does.

{f"Signature: {signature}" if signature else ""}
{f"Docstring: {docstring}" if docstring else ""}

Code:
{node_text[:3000]}{"..." if len(node_text) > 3000 else ""}

Directly return the summary, do not include any other text."""

    response = await ChatGPT_API_async(model, prompt)
    return response


async def generate_summaries_for_code_structure(structure: dict, summary_token_threshold: int, model: str) -> dict:
    """Generate summaries for all nodes in a code structure."""
    nodes = structure_to_list([structure] if isinstance(structure, dict) else structure)

    # Filter to only code nodes (not directories/files at top level unless they have meaningful content)
    code_nodes = [n for n in nodes if n.get('type') in ['class', 'function', 'method', 'interface', 'enum', 'file']]

    tasks = [get_code_node_summary(node, summary_token_threshold, model) for node in code_nodes]
    summaries = await asyncio.gather(*tasks)

    for node, summary in zip(code_nodes, summaries):
        if node.get('nodes'):
            node['prefix_summary'] = summary
        else:
            node['summary'] = summary

    return structure


async def code_to_tree(
    path: str,
    if_thinning: bool = False,
    min_token_threshold: int = 5000,
    if_add_node_summary: str = 'no',
    summary_token_threshold: int = 200,
    model: str = 'gpt-4o-2024-11-20',
    if_add_doc_description: str = 'no',
    if_add_node_text: str = 'no',
    if_add_node_id: str = 'yes'
) -> dict:
    """
    Main entry point for processing Python code into a tree structure.

    Args:
        path: Path to a Python file or directory
        if_thinning: Whether to apply tree thinning for small nodes
        min_token_threshold: Minimum token threshold for thinning
        if_add_node_summary: Whether to generate summaries ('yes' or 'no')
        summary_token_threshold: Token threshold for summary generation
        model: LLM model to use for summaries
        if_add_doc_description: Whether to add document description ('yes' or 'no')
        if_add_node_text: Whether to include source code in output ('yes' or 'no')
        if_add_node_id: Whether to include node IDs ('yes' or 'no')

    Returns:
        Dictionary with doc_name and structure
    """
    path = os.path.abspath(path)

    # Build the tree structure
    if os.path.isfile(path):
        if not path.endswith(('.py', '.java', '.kt', '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
            raise ValueError("File extension not supported")
        structure = build_file_tree(path, model)
        doc_name = os.path.splitext(os.path.basename(path))[0]
    elif os.path.isdir(path):
        structure = build_directory_tree(path, model)
        doc_name = os.path.basename(os.path.normpath(path))
    else:
        raise ValueError(f"Path does not exist: {path}")

    if structure is None:
        raise ValueError(f"Failed to process path: {path}")

    # Apply tree thinning if requested
    if if_thinning:
        print("Applying tree thinning...")
        structure = tree_thinning_for_code(structure, min_token_threshold, model)

    # Clean empty nodes
    structure = clean_empty_nodes(structure)

    # Add node IDs
    if if_add_node_id == 'yes':
        write_node_id([structure] if isinstance(structure, dict) else structure)

    # Define field order for output
    base_order = ['title', 'node_id', 'type', 'signature', 'docstring', 'decorators',
                  'start_line', 'end_line', 'summary', 'prefix_summary', 'text', 'path', 'nodes']

    # Generate summaries if requested
    if if_add_node_summary == 'yes':
        print("Generating summaries...")
        structure = await generate_summaries_for_code_structure(structure, summary_token_threshold, model)

    # Preserve imports text as summary
    structure = preserve_imports_text(structure)

    # Format structure
    structure = format_structure(structure, order=base_order)

    # Remove text if not requested
    if if_add_node_text == 'no':
        structure = remove_text_from_structure(structure)

    # Remove path field from output (it was used internally)
    structure = remove_path_from_structure(structure)

    # Generate document description if requested
    if if_add_doc_description == 'yes':
        print("Generating document description...")
        clean_structure = create_clean_structure_for_description(structure)
        doc_description = generate_doc_description(clean_structure, model=model)
        return {
            'doc_name': doc_name,
            'doc_description': doc_description,
            'structure': [structure] if isinstance(structure, dict) else structure
        }

    return {
        'doc_name': doc_name,
        'structure': [structure] if isinstance(structure, dict) else structure
    }


def remove_text_from_structure(structure):
    """Remove 'text' field from all nodes in the structure."""
    if isinstance(structure, dict):
        structure.pop('text', None)
        if 'nodes' in structure:
            structure['nodes'] = [remove_text_from_structure(n) for n in structure['nodes']]
    elif isinstance(structure, list):
        return [remove_text_from_structure(item) for item in structure]
    return structure


def remove_path_from_structure(structure):
    """Remove 'path' field from all nodes in the structure."""
    if isinstance(structure, dict):
        structure.pop('path', None)
        if 'nodes' in structure:
            structure['nodes'] = [remove_path_from_structure(n) for n in structure['nodes']]
    elif isinstance(structure, list):
        return [remove_path_from_structure(item) for item in structure]
    return structure


def preserve_imports_text(structure):
    """Copy text to summary for imports nodes so it survives text removal."""
    if isinstance(structure, dict):
        if structure.get('type') == 'imports':
            # Use prefix_summary to ensure it appears at the top if there were children (though imports usually don't have children)
            # But strict schema uses 'summary' for leaves. Text can be multiline.
            structure['summary'] = structure.get('text', '').strip()
            
        if 'nodes' in structure:
            # Recursively process children
            for child in structure['nodes']:
                preserve_imports_text(child)
    elif isinstance(structure, list):
        for item in structure:
            preserve_imports_text(item)
    return structure


if __name__ == "__main__":
    import json

    # Test on the pageindex directory
    CODE_PATH = os.path.dirname(__file__)

    MODEL = "gpt-4o-2024-11-20"
    IF_THINNING = False
    THINNING_THRESHOLD = 5000
    SUMMARY_TOKEN_THRESHOLD = 200
    IF_SUMMARY = False
    IF_TEXT = True

    tree_structure = asyncio.run(code_to_tree(
        path=CODE_PATH,
        if_thinning=IF_THINNING,
        min_token_threshold=THINNING_THRESHOLD,
        if_add_node_summary='yes' if IF_SUMMARY else 'no',
        summary_token_threshold=SUMMARY_TOKEN_THRESHOLD,
        model=MODEL,
        if_add_node_text='yes' if IF_TEXT else 'no'
    ))

    print('\n' + '='*60)
    print('TREE STRUCTURE')
    print('='*60)

    # Print simplified version
    def print_tree(node, indent=0):
        prefix = '  ' * indent
        node_type = node.get('type', 'unknown')
        title = node.get('title', 'Unknown')
        print(f"{prefix}- [{node_type}] {title}")
        for child in node.get('nodes', []):
            print_tree(child, indent + 1)

    for node in tree_structure['structure']:
        print_tree(node)

    # Save to file
    output_path = os.path.join(os.path.dirname(__file__), '..', 'results', f'{tree_structure["doc_name"]}_code_structure.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tree_structure, f, indent=2, ensure_ascii=False)

    print(f"\nTree structure saved to: {output_path}")
