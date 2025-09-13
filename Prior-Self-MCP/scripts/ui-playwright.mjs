// Minimal Playwright UI smoke for Prior‑Self MCP
// Usage:
//   node Prior-Self-MCP/scripts/ui-playwright.mjs
// Requires: npm i -D playwright (and: npx playwright install --with-deps chromium)

import { chromium } from 'playwright';

const BASE = process.env.PRIOR_BASE || 'http://127.0.0.1:7070';

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

    console.log('Call search_previous_chats…');
    await page.getByRole('textbox', { name: 'Tool name' }).fill('search_previous_chats');
    await page.getByRole('textbox', { name: 'Arguments (JSON)' }).fill(j({
      query: 'tokens',
      project: 'Smoke',
      k: 5
    }));
    await page.getByRole('button', { name: 'tools/call' }).click();
    await page.waitForTimeout(150);
    const out1 = await page.getByText('{ "jsonrpc": "2.0", "id": 3').first().textContent();
    if (!out1.includes('structuredContent')) throw new Error('Expected structuredContent in response');
    console.log('  search_previous_chats OK');

    console.log('Call get_chat_context…');
    await page.getByRole('textbox', { name: 'Tool name' }).fill('get_chat_context');
    await page.getByRole('textbox', { name: 'Arguments (JSON)' }).fill(j({ chat_id: 's1' }));
    await page.getByRole('button', { name: 'tools/call' }).click();
    await page.waitForTimeout(150);
    const out2 = await page.getByText('{ "jsonrpc": "2.0", "id": 3').first().textContent();
    if (!out2.includes('messages')) throw new Error('Expected messages in response');
    console.log('  get_chat_context OK');

    console.log('UI smoke passed.');
  } finally {
    await browser.close();
  }
}

main().catch((e) => { console.error(e); process.exit(1); });

