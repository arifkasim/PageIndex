import argparse
import os
import json
import asyncio
import sys
import atexit
from pageindex import *
from pageindex.page_index_md import md_to_tree
from pageindex.page_index_code import code_to_tree

# Suppress SSL cleanup errors on exit (Python 3.9 issue)
if sys.version_info < (3, 10):
    import warnings
    warnings.filterwarnings('ignore', message='.*SSL.*')

    # Suppress stderr during Python shutdown to hide SSL transport errors
    _original_stderr = sys.stderr
    class _NullWriter:
        def write(self, *args, **kwargs): pass
        def flush(self, *args, **kwargs): pass

    def _suppress_ssl_errors_on_exit():
        sys.stderr = _NullWriter()

    atexit.register(_suppress_ssl_errors_on_exit)


def run_async(coro):
    """
    Run async coroutine with proper cleanup to avoid SSL errors on Python 3.9.
    """
    if sys.version_info >= (3, 10):
        return asyncio.run(coro)

    # For Python 3.9 and earlier, handle cleanup manually
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Suppress SSL transport errors during cleanup (harmless but noisy)
    def ignore_ssl_error(loop, context):
        exc = context.get('exception')
        if exc and 'SSL' in str(type(exc).__name__):
            return
        if 'transport' in str(context.get('message', '')).lower():
            return
        loop.default_exception_handler(context)

    loop.set_exception_handler(ignore_ssl_error)

    try:
        return loop.run_until_complete(coro)
    finally:
        # Clean up pending tasks
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        # Give time for SSL connections to close gracefully
        try:
            loop.run_until_complete(asyncio.sleep(0.25))
        except Exception:
            pass
        loop.close()

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process PDF, Markdown, or Python code and generate structure')
    parser.add_argument('--pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument('--md_path', type=str, help='Path to the Markdown file')
    parser.add_argument('--code_path', type=str, help='Path to Python file or directory')

    parser.add_argument('--model', type=str, default='gpt-4o-2024-11-20',
                      help='Model to use (supports multiple providers via LiteLLM: '
                           'anthropic/claude-sonnet-4-20250514, gemini/gemini-2.0-flash, '
                           'gpt-4o, ollama/llama3.1, etc.)')

    parser.add_argument('--toc-check-pages', type=int, default=20, 
                      help='Number of pages to check for table of contents (PDF only)')
    parser.add_argument('--max-pages-per-node', type=int, default=10,
                      help='Maximum number of pages per node (PDF only)')
    parser.add_argument('--max-tokens-per-node', type=int, default=20000,
                      help='Maximum number of tokens per node (PDF only)')

    parser.add_argument('--if-add-node-id', type=str, default='yes',
                      help='Whether to add node id to the node')
    parser.add_argument('--if-add-node-summary', type=str, default='yes',
                      help='Whether to add summary to the node')
    parser.add_argument('--if-add-doc-description', type=str, default='no',
                      help='Whether to add doc description to the doc')
    parser.add_argument('--if-add-node-text', type=str, default='no',
                      help='Whether to add text to the node')
                      
    # Markdown specific arguments
    parser.add_argument('--if-thinning', type=str, default='no',
                      help='Whether to apply tree thinning for markdown (markdown only)')
    parser.add_argument('--thinning-threshold', type=int, default=5000,
                      help='Minimum token threshold for thinning (markdown only)')
    parser.add_argument('--summary-token-threshold', type=int, default=200,
                      help='Token threshold for generating summaries (markdown only)')
    args = parser.parse_args()

    # Validate that exactly one file type is specified
    specified_paths = [args.pdf_path, args.md_path, args.code_path]
    num_specified = sum(1 for p in specified_paths if p is not None)
    if num_specified == 0:
        raise ValueError("One of --pdf_path, --md_path, or --code_path must be specified")
    if num_specified > 1:
        raise ValueError("Only one of --pdf_path, --md_path, or --code_path can be specified")
    
    if args.pdf_path:
        # Validate PDF file
        if not args.pdf_path.lower().endswith('.pdf'):
            raise ValueError("PDF file must have .pdf extension")
        if not os.path.isfile(args.pdf_path):
            raise ValueError(f"PDF file not found: {args.pdf_path}")
            
        # Process PDF file
        # Configure options
        opt = config(
            model=args.model,
            toc_check_page_num=args.toc_check_pages,
            max_page_num_each_node=args.max_pages_per_node,
            max_token_num_each_node=args.max_tokens_per_node,
            if_add_node_id=args.if_add_node_id,
            if_add_node_summary=args.if_add_node_summary,
            if_add_doc_description=args.if_add_doc_description,
            if_add_node_text=args.if_add_node_text
        )

        # Process the PDF
        toc_with_page_number = page_index_main(args.pdf_path, opt)
        print('Parsing done, saving to file...')
        
        # Save results
        pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{pdf_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2)
        
        print(f'Tree structure saved to: {output_file}')
            
    elif args.md_path:
        # Validate Markdown file
        if not args.md_path.lower().endswith(('.md', '.markdown')):
            raise ValueError("Markdown file must have .md or .markdown extension")
        if not os.path.isfile(args.md_path):
            raise ValueError(f"Markdown file not found: {args.md_path}")
            
        # Process markdown file
        print('Processing markdown file...')
        
        # Use ConfigLoader to get consistent defaults (matching PDF behavior)
        from pageindex.utils import ConfigLoader
        config_loader = ConfigLoader()
        
        # Create options dict with user args
        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id
        }
        
        # Load config with defaults from config.yaml
        opt = config_loader.load(user_opt)
        
        toc_with_page_number = run_async(md_to_tree(
            md_path=args.md_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=opt.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id
        ))
        
        print('Parsing done, saving to file...')
        
        # Save results
        md_name = os.path.splitext(os.path.basename(args.md_path))[0]    
        output_dir = './results'
        output_file = f'{output_dir}/{md_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)

        print(f'Tree structure saved to: {output_file}')

    elif args.code_path:
        # Validate Python file or directory
        if not os.path.exists(args.code_path):
            raise ValueError(f"Path not found: {args.code_path}")
        if os.path.isfile(args.code_path) and not args.code_path.lower().endswith(('.py', '.java', '.kt', '.c', '.h', '.cpp', '.hpp', '.cc', '.cxx')):
            raise ValueError("File extension not supported")

        # Process Python code
        print('Processing Python code...')

        # Use ConfigLoader to get consistent defaults
        from pageindex.utils import ConfigLoader
        config_loader = ConfigLoader()

        # Create options dict with user args
        user_opt = {
            'model': args.model,
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id
        }

        # Load config with defaults from config.yaml
        opt = config_loader.load(user_opt)

        toc_with_page_number = run_async(code_to_tree(
            path=args.code_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=opt.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id
        ))

        print('Parsing done, saving to file...')

        # Save results
        if os.path.isfile(args.code_path):
            code_name = os.path.splitext(os.path.basename(args.code_path))[0]
        else:
            code_name = os.path.basename(os.path.normpath(args.code_path))
        output_dir = './results'
        output_file = f'{output_dir}/{code_name}_code_structure.json'
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)

        print(f'Tree structure saved to: {output_file}')