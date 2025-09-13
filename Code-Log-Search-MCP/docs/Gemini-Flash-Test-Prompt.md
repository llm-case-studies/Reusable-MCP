Gemini Flash — Code‑Log‑Search MCP Test Plan Prompt

Goal
- Design and execute a comprehensive test plan for the Code‑Log‑Search MCP tools using Gemini Flash, generating ~100 diverse test cases and documenting results.

Context
- MCP server: code-log-search (HTTP MCP at http://127.0.0.1:7080/mcp)
- Tools:
  - search_code: { query: string, root?: string, globs?: string[], maxResults?: number, contextLines?: number, literal?: boolean }
  - search_logs: { query: string, date?: YYYYMMDD, mode?: string, maxResults?: number }
- Default roots for this project:
  - CODE_ROOT: /home/alex/Projects/Reusable-MCP (use this unless otherwise stated)
  - LOGS_ROOT: /home/alex/Projects/Reusable-MCP/Code-Log-Search-MCP/logs

Instructions to Gemini (paste as a system or user message)
"""
You have access to the MCP server "code-log-search" with tools:
- search_code: { query, root?, globs?, maxResults?, contextLines?, literal? }
- search_logs: { query, date?, mode?, maxResults? }

Requirements
- Generate approximately 100 distinct test cases covering:
  - Patterns: single token, multi-token with regex (e.g., README|MCP), special characters, anchors, word boundaries.
  - literal flag: both literal=false (regex) and literal=true (fixed strings) cases.
  - globs: include/exclude via ['*.py','*.md','*.txt'] combinations.
  - root variations: default project root, nested subfolders.
  - contextLines: [0,1,2] and verify presence/absence of context.
  - maxResults: small caps (e.g., 1, 5, 10) and larger caps (e.g., 50).
  - logs search: deterministic runs using known JSONL files in LOGS_ROOT with date filters (seed a file if needed: 20250101.jsonl).

Execution policy
- For EACH test case, return ONLY ONE JSON MCP tool call in the form:
  {"tool":"code-log-search/<name>","params":{...}}
- Do not return prose around calls during the test execution phase. If a call fails, adapt parameters and retry up to once.
- Use small maxResults and contextLines where possible to keep outputs small.

Documentation
- After executing all test calls, produce a concise RESULTS DOCUMENT in Markdown including:
  - Summary table: counts by tool, pass/fail/error, retries.
  - Representative examples for each category (regex vs literal, glob variants, logs with date/mode).
  - Notes on edge cases and any observed quirks.
  - Place results under path: Code-Log-Search-MCP/docs/Gemini-Flash-Test-Results.md (if you can write files via a Shell tool). If file write isn’t available, include the document in your final message so it can be saved manually.

Safety and formatting
- Keep each tool call valid per schemas above.
- Keep test inputs focused on this repository (do not attempt network access).
- Minimize token usage: prefer maxResults≤10, contextLines≤2.
"""

Tips
- For logs testing: create a file 20250101.jsonl in LOGS_ROOT with a few entries (e.g., {"mode":"brainstorm","msg":"ok"}) so search_logs with date="20250101" and mode="brainstorm" is deterministic.
- For multi‑keyword literal tests, set literal=true and use a simple query like "README MCP" with globs to constrain search.

