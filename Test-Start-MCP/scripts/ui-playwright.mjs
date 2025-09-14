/*
  Playwright UI Smoke for Test-Start-MCP

  What it does:
  - Opens /mcp_ui
  - initialize → verifies protocolVersion
  - tools/list → verifies run_script tool present
  - tools/call(run_script) → executes an allow‑listed script with safe flags and checks result
  - Verifies /healthz and /actions/list_allowed via fetch

  Usage:
    npm i -D playwright
    npx playwright install --with-deps chromium
    node Test-Start-MCP/scripts/ui-playwright.mjs

  Env:
    TSM_URL              Base URL (default http://127.0.0.1:7060)
    TSM_TOKEN            Optional bearer token; stored in localStorage for UI
    TSM_PLAYWRIGHT_SCRIPT  Absolute path to an allow‑listed script. If unset, a reasonable default is used.
*/

import { chromium } from 'playwright'

const BASE = process.env.TSM_URL || 'http://127.0.0.1:7060'
const TOKEN = process.env.TSM_TOKEN || ''
// Default aligns with handover; override with TSM_PLAYWRIGHT_SCRIPT if needed
const DEFAULT_SCRIPT = process.env.TSM_PLAYWRIGHT_SCRIPT || '/home/alex/Projects/Reusable-MCP/Memory-MCP/run-tests-and-server.sh'

function j(o){ try { return JSON.stringify(o, null, 2) } catch { return String(o) } }

async function run(){
  const browser = await chromium.launch({ headless: process.env.HEADFUL ? false : true })
  const ctx = await browser.newContext()
  const page = await ctx.newPage()

  console.log(`[SMOKE] Visiting ${BASE}/mcp_ui`)
  // Set token before navigating so fetch uses it
  if (TOKEN) {
    await page.addInitScript(token => localStorage.setItem('TSM_TOKEN', token), TOKEN)
  }
  await page.goto(`${BASE}/mcp_ui`, { waitUntil: 'domcontentloaded', timeout: 30_000 })

  // initialize
  console.log('[SMOKE] initialize')
  await page.getByText('initialize', { exact: true }).click()
  await page.waitForTimeout(500)
  const initText = await page.locator('#initOut').textContent()
  if (!initText || !initText.includes('protocolVersion')) {
    throw new Error('initialize did not return protocolVersion')
  }

  // tools/list
  console.log('[SMOKE] tools/list')
  await page.getByText('tools/list', { exact: true }).click()
  await page.waitForTimeout(500)
  const toolsText = await page.locator('#toolsOut').textContent()
  if (!toolsText || !toolsText.includes('run_script')) {
    throw new Error('tools/list did not include run_script')
  }

  // Prepare a safe run_script call
  const argsJson = {
    path: DEFAULT_SCRIPT,
    args: ["--no-tests", "--smoke"],
    timeout_ms: 30000
  }

  console.log('[SMOKE] tools/call(run_script)')
  await page.locator('#tname').fill('run_script')
  await page.locator('#targs').fill(j(argsJson))
  await page.getByText('tools/call', { exact: true }).click()
  await page.waitForTimeout(1000)
  const callText = await page.locator('#callOut').textContent()
  if (!callText) throw new Error('tools/call returned empty response')
  let callObj
  try { callObj = JSON.parse(callText) } catch { /* UI might stringify nicely already */ }
  const ok = callText.includes('structuredContent') || (callObj && callObj.result && callObj.result.structuredContent)
  if (!ok) throw new Error('tools/call did not include structuredContent')

  // Verify REST endpoints quickly via page fetch
  console.log('[SMOKE] /healthz + /actions/list_allowed')
  const health = await page.evaluate(async () => {
    const r = await fetch('/healthz')
    return await r.json()
  })
  if (!health || !('ok' in health)) throw new Error('healthz missing ok')

  const allowed = await page.evaluate(async () => {
    const r = await fetch('/actions/list_allowed', { method: 'POST', headers: { 'Content-Type':'application/json' }, body: '{}' })
    return await r.json()
  })
  if (!allowed || !Array.isArray(allowed.scripts)) throw new Error('list_allowed missing scripts')

  // Exercise /start interactive page
  console.log(`[SMOKE] Visiting ${BASE}/start`)
  await page.goto(`${BASE}/start`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  // List allowed
  await page.getByText('List Allowed', { exact: true }).click()
  await page.waitForTimeout(300)
  const allowedText = await page.locator('#allowedOut').textContent()
  if (!allowedText || !allowedText.includes('scripts')) throw new Error('allowed scripts missing on /start')
  // Run Script (REST)
  await page.locator('#sp').fill(DEFAULT_SCRIPT)
  await page.locator('#sa').fill('--no-tests,--smoke')
  await page.getByText('POST /actions/run_script', { exact: true }).click()
  await page.waitForTimeout(800)
  const runRes = await page.locator('#runOut').textContent()
  if (!runRes || !(runRes.includes('exitCode') || runRes.includes('duration_ms'))) throw new Error('run_script REST missing fields')
  // Run Script (SSE)
  await page.locator('#ssp').fill(DEFAULT_SCRIPT)
  await page.locator('#ssa').fill('--no-tests,--smoke')
  await page.getByText('Open SSE', { exact: true }).click()
  await page.waitForTimeout(1200)
  const so = await page.locator('#streamOut').textContent()
  if (!so || (!so.includes('[stdout]') && !so.includes('end'))) throw new Error('SSE output missing')
  await page.getByText('Close SSE', { exact: true }).click()
  // Stats & Health buttons
  await page.getByText('POST /actions/get_stats', { exact: true }).click()
  await page.waitForTimeout(300)
  const statsText = await page.locator('#statsOut').textContent()
  if (!statsText || !statsText.includes('total_executions')) throw new Error('stats missing total_executions')
  await page.getByText('GET /healthz', { exact: true }).click()
  await page.waitForTimeout(300)
  const healthText2 = await page.locator('#healthOut').textContent()
  if (!healthText2 || !healthText2.includes('ok')) throw new Error('health missing ok on /start')

  console.log('[SMOKE] PASS')
  await browser.close()
}

run().catch(async err => {
  console.error('[SMOKE] FAIL', err?.message || err)
  process.exit(1)
})
