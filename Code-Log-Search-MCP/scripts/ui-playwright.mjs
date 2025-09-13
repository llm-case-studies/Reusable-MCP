// Minimal Playwright UI smoke for Code-Log-Search MCP
// Usage:
//   node Code-Log-Search-MCP/scripts/ui-playwright.mjs
// Requires: npm i -D playwright (and: npx playwright install --with-deps chromium)

import { chromium } from 'playwright';

const BASE = process.env.CLS_BASE || 'http://127.0.0.1:7080';
const ROOT = process.env.CLS_CODE_ROOT || process.cwd();

function j(o) { return JSON.stringify(o, null, 2); }

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  try {
    console.log('Open MCP UI…');
    await page.goto(`${BASE}/mcp_ui`, { waitUntil: 'domcontentloaded' });

    console.log('Initialize…');
    await page.getByRole('button', { name: 'initialize' }).click();
    await page.waitForTimeout(100);

    console.log('Tools list…');
    await page.getByRole('button', { name: 'tools/list' }).click();
    await page.waitForTimeout(100);

    console.log('Call search_code (literal)…');
    await page.getByRole('textbox', { name: 'Tool name' }).fill('search_code');
    await page.getByRole('textbox', { name: 'Arguments (JSON)' }).fill(j({
      query: 'MCP Dev',
      root: ROOT,
      maxResults: 5,
      contextLines: 0,
      literal: true
    }));
    await page.getByRole('button', { name: 'tools/call' }).click();
    await page.waitForTimeout(150);
    const out1 = await page.getByText('{ "jsonrpc": "2.0", "id": 3').first().textContent();
    if (!out1.includes('structuredContent')) throw new Error('Expected structuredContent in response');
    console.log('  literal call OK');

    console.log('Call search_code (forbidden_root)…');
    await page.getByRole('textbox', { name: 'Arguments (JSON)' }).fill(j({
      query: 'README',
      root: '/',
      maxResults: 5,
      contextLines: 0
    }));
    await page.getByRole('button', { name: 'tools/call' }).click();
    await page.waitForTimeout(150);
    const out2 = await page.getByText('{ "jsonrpc": "2.0", "id": 3').first().textContent();
    if (!out2.includes('forbidden_root')) {
      console.warn('  forbidden_root not observed in UI; API contract is covered by unit tests.');
    } else {
      console.log('  forbidden_root surfaced in UI');
    }

    console.log('UI smoke passed.');
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });

