import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {it,expect,vi,afterEach} from 'vitest';
import App from '../src/App';
afterEach(()=>vi.unstubAllGlobals());
function mock(serverFailure=false,duplicate=false){
  const fetch=vi.fn(async(path:string,options?:RequestInit)=>{
    if(path.includes('/revenues'))return new Response(JSON.stringify([{revenue_code:'WATER',name:'Water supply',category:'WATER'}]));
    if(path.includes('/payers'))return new Response(JSON.stringify([{payer_id:1,full_name:'Amina Demo',tin:'TEST-001',phone:'0700000001'}]));
    const lines=JSON.parse(options?.body as string);
    if(serverFailure)return new Response(JSON.stringify({detail:'Service unavailable'}),{status:503});
    return new Response(JSON.stringify({received:lines.length,accepted:duplicate?0:lines.length,rejected:duplicate?lines.length:0,results:lines.map((line:{external_ref:string;amount:string})=>({...line,status:duplicate?'REJECTED':'ACCEPTED',payment_id:'receipt-001',reasons:duplicate?['duplicate external reference']:[]}))}));
  });vi.stubGlobal('fetch',fetch);return fetch;
}
async function start(){
  const user=userEvent.setup();render(<App/>);
  await user.type(screen.getByLabelText('Officer API key'),'test-only');await user.click(screen.getByRole('button',{name:/Connect to revenue/}));
  await user.type(await screen.findByLabelText('TIN, phone or water account'),'TEST-001');await user.click(screen.getByRole('button',{name:'Search'}));
  await user.click(await screen.findByRole('button',{name:/Amina Demo/}));await user.selectOptions(screen.getByLabelText('Revenue type'),'WATER');await user.click(screen.getByRole('button',{name:'Payment lines'}));return user;
}
it('searches payer and submits multiple lines with receipt',async()=>{
  mock();const user=await start();await user.type(screen.getAllByLabelText('Amount (USD)')[0],'10');await user.type(screen.getAllByLabelText('External reference')[0],'FIRST');
  await user.click(screen.getByRole('button',{name:'Add payment line'}));await user.type(screen.getAllByLabelText('Amount (USD)')[1],'20');await user.type(screen.getAllByLabelText('External reference')[1],'SECOND');
  await user.click(screen.getByRole('button',{name:'Review payment'}));await user.click(screen.getByRole('button',{name:'Confirm & record'}));
  expect(await screen.findByRole('heading',{name:'Payment recorded'})).toBeVisible();expect(screen.getByRole('status')).toHaveTextContent('2 accepted');expect(screen.getByRole('button',{name:'Print receipt'})).toBeEnabled();
});
it('blocks invalid amount',async()=>{mock();const user=await start();await user.type(screen.getByLabelText('Amount (USD)'),'0');await user.click(screen.getByRole('button',{name:'Review payment'}));expect(screen.getByRole('alert')).toHaveTextContent('positive amount');});
it('displays server duplicate reference',async()=>{mock(false,true);const user=await start();await user.type(screen.getByLabelText('Amount (USD)'),'10');await user.type(screen.getByLabelText('External reference'),'DUP');await user.click(screen.getByRole('button',{name:'Review payment'}));await user.click(screen.getByRole('button',{name:'Confirm & record'}));expect(await screen.findByText('duplicate external reference')).toBeVisible();expect(screen.getByRole('button',{name:'Print receipt'})).toBeDisabled();});
it('preserves idempotency key and body after server failure',async()=>{const fetch=mock(true);const user=await start();await user.type(screen.getByLabelText('Amount (USD)'),'10');await user.type(screen.getByLabelText('External reference'),'RETRY');await user.click(screen.getByRole('button',{name:'Review payment'}));await user.click(screen.getByRole('button',{name:'Confirm & record'}));expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');await user.click(screen.getByRole('button',{name:'Retry same payment'}));const calls=fetch.mock.calls.filter(([path])=>path.includes('/bulk'));expect(calls[0][1]).toEqual(calls[1][1]);});
