export type Payer={payer_id:number;full_name:string;tin:string;phone:string};
export type Revenue={revenue_code:string;name:string;category:string};
export type Line={id:string;amount:string;channel:string;external_ref:string};
export type Result={status:'ACCEPTED'|'REJECTED';external_ref:string;payment_id?:string;amount?:string;reasons:string[]};
export type Summary={received:number;accepted:number;rejected:number;results:Result[]};
const base=import.meta.env.VITE_API_URL||'http://localhost:8000';
export async function api<T>(path:string,key:string,options:RequestInit={}):Promise<T>{
  let response:Response;
  try {response=await fetch(base+path,{...options,headers:{'Content-Type':'application/json','X-Officer-Key':key,...options.headers}});}
  catch {throw new Error('Unable to reach the revenue service. Check your connection and retry.');}
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:`Request failed (${response.status}).`);
  return data;
}
export function cents(value:string):number{return Math.round(Number(value)*100);}
export function validate(lines:Line[]):string[]{
  const refs=new Set<string>();
  return lines.flatMap((line,index)=>{
    const errors:string[]=[];
    if(!/^\d+(\.\d{1,2})?$/.test(line.amount)||cents(line.amount)<=0||!Number.isSafeInteger(cents(line.amount))) errors.push(`Line ${index+1}: enter a positive amount with up to two decimals.`);
    const ref=line.external_ref.trim();
    if(!ref||ref.length>100) errors.push(`Line ${index+1}: enter an external reference (up to 100 characters).`);
    if(refs.has(ref)) errors.push(`Line ${index+1}: duplicate external reference.`);
    refs.add(ref);return errors;
  });
}
export const money=(value:number)=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(value/100);
