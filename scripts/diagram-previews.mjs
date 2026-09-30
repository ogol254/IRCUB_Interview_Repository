import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const require=createRequire(resolve('section_01_technical/frontend/package.json'));
const {chromium}=require('playwright');
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1600,height:1100}});
for(const name of ['executive-architecture','full-payment-business']){
 await page.goto(pathToFileURL(resolve(`section_03_system_design/diagrams/${name}.svg`)).href);
 await page.locator('svg').screenshot({path:`section_03_system_design/diagrams/${name}.png`});
}
await browser.close();
