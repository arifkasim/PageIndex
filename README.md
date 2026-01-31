<div align="center">
  
<a href="https://vectify.ai/pageindex" target="_blank">
  <img src="https://github.com/user-attachments/assets/46201e72-675b-43bc-bfbd-081cc6b65a1d" alt="PageIndex Banner" />
</a>

<br/>
<br/>

<p align="center">
  <a href="https://trendshift.io/repositories/14736" target="_blank"><img src="https://trendshift.io/api/badge/repositories/14736" alt="VectifyAI%2FPageIndex | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
</p>

# PageIndex: Codebase into Context for AI

<p align="center"><b>Hierarchical Code Indexing&nbsp; ◦ &nbsp;AST-Based Parsing&nbsp; ◦ &nbsp;Multi-Language Support</b></p>

<h4 align="center">
  <a href="https://vectify.ai">🏠 Homepage</a>&nbsp; • &nbsp;
  <a href="https://docs.pageindex.ai">📚 Docs</a>&nbsp; • &nbsp;
  <a href="https://discord.com/invite/VuXuf29EUj">💬 Discord</a>
</h4>
  
</div>

---

# 📑 Introduction

**PageIndex** transforms your entire codebase into a structured **hierarchical tree** (JSON) optimized for AI Agents and LLMs. 

Instead of treating code as flat chunks of text, PageIndex parses the **Abstract Syntax Tree (AST)** or structure of your files to understand the relationships between **Classes**, **Functions**, **Methods**, and **Interfaces**. This allows your AI agents to navigate your codebase logically—understanding that method `B` belongs to Class `A`, and correctly retrieving the context they need.

### 🚀 Supported Languages

| Language | Extension | Parsing Method | Features |
| :--- | :--- | :--- | :--- |
| **Python** | `.py` | Built-in `ast` module | Classes, Functions, Decorators, Docstrings |
| **Java** | `.java` | `javalang` library | Classes, Interfaces, Enums, Methods, Annotations |
| **Kotlin** | `.kt` | Regex & Brace Counting | Classes, Data Classes, Objects, Functions |

---

# 📦 Installation

```bash
# Clone the repository
git clone https://github.com/arifkasim/PageIndex.git
cd PageIndex

# Install dependencies
pip3 install -r requirements.txt
```

> **Note**: For Java support, `javalang` will be installed automatically with the requirements.

---

# ⚙️ Usage

You can generate a structure tree for a single file or a recursively scanned directory.

### 1. Parse a Project Directory
Scan an entire folder and generate a unified JSON tree containing all supported files (`.py`, `.java`, `.kt`).

```bash
python3 run_pageindex.py --code_path /path/to/your/project/src
```

### 2. Parse a Single File

```bash
# Python
python3 run_pageindex.py --code_path /path/to/script.py

# Java
python3 run_pageindex.py --code_path /path/to/App.java

# Kotlin
python3 run_pageindex.py --code_path /path/to/Utils.kt
```

---

# 🌲 Structure Output

PageIndex generates a JSON output that mirrors the semantic structure of your code.

**Example Output (Simplified):**

```jsonc
{
  "doc_name": "MyProject",
  "structure": [
    {
      "title": "UserService.java",
      "type": "file",
      "path": "src/main/java/com/app/UserService.java",
      "nodes": [
        {
          "title": "UserService",
          "type": "class",
          "docstring": "/** Handles user operations */",
          "nodes": [
            {
              "title": "createUser()",
              "type": "method",
              "signature": "public User createUser(String name, int age)",
              "start_line": 15,
              "end_line": 20
            }
          ]
        }
      ]
    },
    {
      "title": "utils.py",
      "type": "file",
      "nodes": [
        {
          "title": "format_data()",
          "type": "function",
          "signature": "def format_data(data: dict) -> str",
          "start_line": 5,
          "end_line": 10
        }
      ]
    }
  ]
}
```

---

# 🔧 Advanced Configuration

You can customize the parsing with optional arguments:

```bash
--model                 LLM model to use for summaries (default: gpt-4o)
--if-add-node-summary   Generate AI summaries for functions/classes (yes/no, default: yes)
--if-add-node-text      Include the raw source code in the JSON node (yes/no, default: no)
```

**Example: Generate descriptions for your code**
```bash
python3 run_pageindex.py --code_path ./src --if-add-node-summary yes
```

---

# ⭐ Support Us

Leave us a star 🌟 if you like our project!

<p>
  <img src="https://github.com/user-attachments/assets/eae4ff38-48ae-4a7c-b19f-eab81201d794" width="80%">
</p>
