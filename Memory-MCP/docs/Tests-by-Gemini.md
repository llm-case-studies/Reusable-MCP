# Memory-MCP Test Report

## Test 1: write_memory (Moderately Sized Entry)

*   **Test Type:** `write_memory`
*   **Key:** `test-large-memory-1`
*   **Project:** `test-project`
*   **Tags:** `["test", "large"]`
*   **Text Length:** 298 characters
*   **Text Content (first 50 chars):** "This is a moderately sized test memory entry..."
*   **Result:** Success

## Test 2: write_memory (Larger Sized Entry)

*   **Test Type:** `write_memory`
*   **Key:** `test-large-memory-2`
*   **Project:** `test-project`
*   **Tags:** `["test", "large"]`
*   **Text Length:** 894 characters
*   **Text Content (first 50 chars):** "This is a larger test memory entry. It contains..."
*   **Result:** Success

## Test 3: write_memory (Even Larger Sized Entry)

*   **Test Type:** `write_memory`
*   **Key:** `test-large-memory-3`
*   **Project:** `test-project`
*   **Tags:** `["test", "large"]`
*   **Text Length:** 1788 characters
*   **Text Content (first 50 chars):** "This is an even larger test memory entry, signi..."
*   **Result:** Success

## Test 4: search_memory (Non-Existent Query)

*   **Test Type:** `search_memory`
*   **Project:** `test-project`
*   **Query:** `non-existent-memory-query`
*   **Result:** Empty list of items (expected behavior)

## Test 5: read_memory (Non-Existent ID)

*   **Test Type:** `read_memory`
*   **ID:** `non-existent-id`
*   **Result:** `null` entry (expected behavior)

## Test 6: write_memory (Small Load Test)

*   **Test Type:** `write_memory` (3 consecutive calls)
*   **Project:** `test-project-load`
*   **Keys:** `test-load-1`, `test-load-2`, `test-load-3`
*   **Text Length:** ~40 characters each
*   **Result:** All successful, no noticeable delay.

## Test 7: write/read/search with Complex Characters

*   **Test Type:** `write_memory`, `read_memory`, `search_memory`
*   **Project:** `test-project-complex`
*   **Key:** `test-complex-chars`
*   **Text Content:** "This is a test with numbers 12345 and special characters: !@#$%^&*()_+{}[]|\":;'<>,.?/~` and some unicode: éàçüö."
*   **Results:**
    *   `write_memory`: Successful.
    *   `read_memory`: Successful.
    *   `search_memory` (multiple keywords "12345 unicode"): Returned empty list (unexpected).
    *   `search_memory` (single keyword "12345"): Successful.
    *   `search_memory` (single keyword "unicode"): Successful.
    *   `search_memory` (special characters "!@#$"): Returned empty list (unexpected).
*   **Conclusion:** `write_memory` and `read_memory` handle complex characters correctly. `search_memory`'s full-text search behavior with multiple keywords and special characters needs further investigation regarding FTS query syntax.
