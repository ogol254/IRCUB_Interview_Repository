import {test,expect} from '@playwright/test';
import fs from 'node:fs';
const env=Object.fromEntries(fs.readFileSync('../../.env','utf8').split(/\r?\n/).filter(l=>l.includes('=')).map(l=>l.split('=')));
for (const origin of ['http://localhost:5173', 'http://127.0.0.1:5173']) {
  test(`officer connects from ${origin}`, async ({page}) => {
    await page.goto(origin);
    await page.getByLabel('Officer API key').fill(env.OFFICER_API_KEY);
    const revenues = page.waitForResponse(response => response.url().endsWith('/api/v1/revenues'));
    await page.getByRole('button', {name: /Connect to revenue/}).click();
    expect((await revenues).status()).toBe(200);
    await expect(page.getByLabel('TIN, phone or water account')).toBeVisible();
    await expect(page.getByText('Unable to reach the revenue service. Check your connection and retry.')).toHaveCount(0);
  });
}
test('real API: search, two collections, receipt and duplicate rejection',async({page})=>{
  await page.goto('/');await page.getByLabel('Officer API key').fill(env.OFFICER_API_KEY);await page.getByRole('button',{name:/Connect to revenue/}).click();
  async function payer(){await page.getByLabel('TIN, phone or water account').fill('WA-001');await page.getByRole('button',{name:'Search'}).click();await page.getByRole('button',{name:/Amina Demo/}).click();await page.getByLabel('Revenue type').selectOption('WATER');await page.getByRole('button',{name:'Payment lines'}).click();}
  await payer();const ref='E2E-'+Date.now();await page.getByLabel('Amount (USD)').fill('12.50');await page.getByLabel('External reference').fill(ref);await page.getByRole('button',{name:'Add payment line'}).click();await page.getByLabel('Amount (USD)').nth(1).fill('7.50');await page.getByLabel('External reference').nth(1).fill(ref+'-2');await page.getByRole('button',{name:'Review payment'}).click();await page.getByRole('button',{name:'Confirm & record'}).click();
  await expect(page.getByRole('heading',{name:'Payment recorded'})).toBeVisible();await expect(page.getByRole('status')).toContainText('2 accepted');await expect(page.getByRole('button',{name:'Print receipt'})).toBeEnabled();
  await page.screenshot({path:'test-results/payment-receipt.png',fullPage:true});await page.emulateMedia({media:'print'});await page.pdf({path:'test-results/receipt.pdf',format:'A4'});await page.emulateMedia({media:'screen'});
  await page.getByRole('button',{name:'New payment'}).click();await payer();await page.getByLabel('Amount (USD)').fill('12.50');await page.getByLabel('External reference').fill(ref);await page.getByRole('button',{name:'Review payment'}).click();await page.getByRole('button',{name:'Confirm & record'}).click();await expect(page.getByText('duplicate external reference',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
