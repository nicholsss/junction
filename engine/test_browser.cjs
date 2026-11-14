/* Real-browser UX contract; starts a temporary server and never posts to GitHub. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const html = fs.readFileSync(path.join(__dirname, '../walkthrough/index.html'));
  const server = http.createServer((req, res) => {
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'}); res.end(html);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless: true,
      ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    for (const width of [1280, 375]) {
      await page.setViewportSize({width, height: 900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const words = await page.locator('#view-receipt').innerText();
      assert.ok(words.split(/\s+/).length < 400, 'Initial review must stay under 400 visible words');
      assert.equal(await page.locator('#copy-comment').isDisabled(), true);
      assert.equal(await page.locator('#evidence').getAttribute('open'), null);
      assert.equal(await page.locator('[name=outcome]:checked').count(), 0);
      if (process.env.REVIEW_SCREENSHOTS) {
        await page.screenshot({path: path.join(process.env.REVIEW_SCREENSHOTS, `review-${width}.png`)});
      }
    }
    await page.check('[name=outcome][value=changes]');
    await page.fill('[name=reason]', 'Qualify the documentation assumption.');
    assert.equal(await page.locator('#copy-comment').isDisabled(), false);
    await page.check('[name=outcome][value=accept]');
    assert.equal(await page.locator('#copy-comment').isDisabled(), true);
    for (const select of await page.locator('[data-refusal] select').all()) await select.selectOption({index: 1});
    for (const radio of await page.locator('[data-finding] input[value=accept_scope]').all()) await radio.check();
    for (const cb of await page.locator('[data-unknown] input').all()) await cb.check();
    assert.equal(await page.locator('#copy-comment').isDisabled(), false);
    await page.check('[name=outcome][value=escalate]');
    assert.equal(await page.locator('#copy-comment').isDisabled(), false);
    assert.doesNotMatch(await page.locator('#comment-preview').textContent(), /REF\d:|OOR\d:|UNK\d:/);
    assert.equal(await page.locator('[name=reason]').inputValue(), 'Qualify the documentation assumption.');
    await page.locator('#evidence > summary').click();
    const overlap = await page.locator('.brief-item').evaluateAll(items => items.some(el => {
      const a = el.children[0].getBoundingClientRect(), b = el.children[1].getBoundingClientRect();
      return a.bottom > b.top + 1;
    }));
    assert.equal(overlap, false, 'Provenance labels must not collide with explanations');
    await page.evaluate(() => {
      const stale = document.createElement('div'); stale.dataset.stale = 'true'; document.body.append(stale);
    });
    await page.fill('[name=reason]', 'Need a domain owner to review the diagnostic policy.');
    assert.equal(await page.locator('#copy-comment').isDisabled(), true);
    assert.match(await page.locator('#dstate').textContent(), /Evidence outdated/);
    assert.deepEqual(errors, []);
    console.log('Browser checks passed: desktop/mobile, word budget, outcomes, provenance spacing and stale guard.');
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
