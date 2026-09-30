// Run from root: node scripts/render-diagrams.mjs
import {readdirSync,mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
const dir='section_03_system_design/diagrams';
for(const file of readdirSync(dir).filter(f=>f.endsWith('.mmd'))){
 const result=spawnSync(process.platform==='win32'?'npx.cmd':'npx',['--yes','--package','@mermaid-js/mermaid-cli@11.12.0','mmdc','-i',path.join(dir,file),'-o',path.join(dir,file.replace('.mmd','.svg')),'-b','white','-w','1600'],{stdio:'inherit',shell:process.platform==='win32'});
 if(result.status!==0)process.exit(result.status||1);
}
