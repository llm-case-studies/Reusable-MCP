/*
  Playwright Admin Smoke for Test-Start-MCP

  Covers:
  - Auth and initial state render
  - Add a path rule under allowed root (probe.sh)
  - Remove the rule
  - Assign a profile overlay to a session
  - Load policy audit tail

  Usage:
    npm i -D playwright
    npx playwright install --with-deps chromium
    node Test-Start-MCP/scripts/ui-playwright-admin.mjs

  Env:
    TSM_URL              Base URL (default http://127.0.0.1:7060)
    TSM_ADMIN_TOKEN      Required admin token; stored in localStorage for /admin
    TSM_ADMIN_TARGET     Optional absolute path to a script under allowed root; default resolves Test-Start-MCP/scripts/probe.sh
    HEADFUL=1            To show the browser
    TSM_PW_OUT           Artifacts directory (default Test-Start-MCP/.pw-artifacts)
*/

import { chromium } from 'playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const BASE = process.env.TSM_URL || 'http://127.0.0.1:7060'
const ADMIN = process.env.TSM_ADMIN_TOKEN || ''
if (!ADMIN) {
  console.error('[ADMIN-SMOKE] Missing TSM_ADMIN_TOKEN');
  process.exit(2)
}
const ART = process.env.TSM_PW_OUT || 'Test-Start-MCP/.pw-artifacts'
const DEFAULT_TARGET = process.env.TSM_ADMIN_TARGET || path.resolve(process.cwd(), 'Test-Start-MCP/scripts/probe.sh')

function j(o){ try { return JSON.stringify(o, null, 2) } catch { return String(o) } }

async function run(){
  const ts = new Date().toISOString().replace(/[:.]/g,'-')
  await fs.mkdir(ART, { recursive: true })
  const browser = await chromium.launch({ headless: process.env.HEADFUL ? false : true })
  const ctx = await browser.newContext()
  const page = await ctx.newPage()
  const shot = (name) => page.screenshot({ path: path.join(ART, `${ts}-${name}.png`) })

  console.log(`[ADMIN-SMOKE] Visiting ${BASE}/admin`)
  await page.addInitScript(token => localStorage.setItem('TSM_ADMIN_TOKEN', token), ADMIN)
  await page.goto(`${BASE}/admin`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await shot('admin-open')

  // Refresh state and ensure HTML rendered
  await page.getByText('Refresh State', { exact: true }).click()
  await page.waitForTimeout(400)
  const stateText = await page.locator('#state').textContent()
  if (!stateText || !stateText.includes('version')) throw new Error('Admin state did not render')

  // Add a path rule for probe.sh with --smoke allowed
  console.log('[ADMIN-SMOKE] Add rule')
  await page.locator('#type').selectOption('path')
  await page.locator('#path').fill(DEFAULT_TARGET)
  await page.locator('#flagsAllowed').fill('--smoke')
  await page.locator('#ttlSec').fill('60')
  await page.getByText('Add Rule', { exact: true }).click()
  await page.waitForTimeout(600)
  const addOut = await page.locator('#addOut').textContent()
  if (!addOut || !addOut.includes('"ok": true')) throw new Error('Add rule did not succeed')
  await shot('admin-add-rule')

  // Refresh and check that rule appears in table
  await page.getByText('Refresh State', { exact: true }).click()
  await page.waitForTimeout(400)
  const rulesHtml = await page.locator('#rules').innerHTML()
  if (!rulesHtml || (!rulesHtml.includes('probe.sh') && !rulesHtml.includes(DEFAULT_TARGET))) {
    console.warn('Rules table did not show the new rule (check path root settings)')
  }
  await shot('admin-rules')

  // Remove first rule if remove button exists
  const removeButtons = page.locator('#rules button')
  if (await removeButtons.count() > 0) {
    console.log('[ADMIN-SMOKE] Remove rule')
    await removeButtons.first().click()
    await page.waitForTimeout(400)
    await page.getByText('Refresh State', { exact: true }).click()
    await page.waitForTimeout(400)
  }

  // Assign profile overlay for a session
  console.log('[ADMIN-SMOKE] Assign profile overlay')
  await page.locator('#sessId').fill('sess-pw')
  // Populate profile list via refresh if not present
  const profileSel = page.locator('#profile')
  if ((await profileSel.locator('option').count()) === 0) {
    await page.getByText('Refresh State', { exact: true }).click()
    await page.waitForTimeout(300)
  }
  // Choose first profile option if any
  const hasOption = await profileSel.locator('option').count()
  if (hasOption > 0) {
    const val = await profileSel.locator('option').first().getAttribute('value')
    await profileSel.selectOption(val || 'tester')
  }
  await page.locator('#sessTtl').fill('120')
  await page.getByText('Assign', { exact: true }).click()
  await page.waitForTimeout(400)
  const profOut = await page.locator('#profileOut').textContent()
  if (!profOut || !profOut.includes('"ok": true')) throw new Error('Assign profile did not succeed')
  await shot('admin-profile')

  // Load audit tail
  await page.getByText("Load Today's Audit", { exact: true }).click()
  await page.waitForTimeout(400)
  const auditText = await page.locator('#audit').textContent()
  if (!auditText || auditText.trim().length === 0) console.warn('Audit tail empty (ok if no writes)')
  await shot('admin-audit')

  console.log('[ADMIN-SMOKE] PASS')
  await browser.close()
}

run().catch(err => {
  console.error('[ADMIN-SMOKE] FAIL', err?.message || err)
  process.exit(1)
})

