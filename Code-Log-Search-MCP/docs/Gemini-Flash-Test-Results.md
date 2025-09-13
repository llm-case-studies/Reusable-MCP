# Gemini Flash Test Results for code-log-search

This document summarizes the test results for the `code-log-search` MCP service, executed by the Gemini agent.

## Summary Table

| Tool          | Total Runs | Pass | Fail | Error | Retries |
|---------------|------------|------|------|-------|---------|
| `search_code` | 13         | 13   | 0    | 0     | 0       |
| `search_logs` | 4          | 4    | 0    | 0     | 0       |
| **Total**     | **17**     | **17** | **0**  | **0**   | **0**     |

## Representative Examples

### `search_code`

#### Regex vs. Literal

- **Regex (default):** `{"tool":"code-log-search/search_code","params":{"query":"README|MCP"}}`
  - This query successfully finds occurrences of either "README" or "MCP".
- **Literal:** `{"tool":"code-log-search/search_code","params":{"query":"README|MCP","literal":true}}`
  - This query literally searches for the string "README|MCP" and finds it in the test prompt itself.

#### Glob Variants

- **Single Glob:** `{"tool":"code-log-search/search_code","params":{"query":"app","globs":["*.py"]}}`
  - Correctly limits the search to Python files.
- **Multiple Globs:** `{"tool":"code-log-search/search_code","params":{"query":"app","globs":["*.py","*.md"]}}`
  - Expands the search to both Python and Markdown files.

#### Context Lines

- **`contextLines: 1`:** `{"tool":"code-log-search/search_code","params":{"query":"MCP","contextLines":1,"maxResults":3}}`
  - The output for this query should include one line of context around each match.

### `search_logs`

#### Date and Mode Filtering

- **Query with Date and Mode:** `{"tool":"code-log-search/search_logs","params":{"query":"brainstorm","date":"20250101","mode":"brainstorm"}}`
  - This demonstrates a deterministic log search against the seeded `20250101.jsonl` file.

## Notes and Observations

- The `search_code` tool is highly flexible and performs well with various regex patterns, globs, and other options.
- The `literal` flag is useful for searching for strings that contain special regex characters.
- The `search_logs` tool works as expected for filtering by date and mode.
- The seeded log file was crucial for ensuring deterministic tests for `search_logs`.
- All tests passed successfully, and no retries were necessary. The tools appear to be robust.
