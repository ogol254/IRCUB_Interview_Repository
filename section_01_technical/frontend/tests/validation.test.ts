import {describe,it,expect} from 'vitest';
import {validate,cents,type Line} from '../src/api';
const line=(amount:string,external_ref='REF'):Line=>({id:'1',amount,external_ref,channel:'BANK'});
describe('financial validation',()=>{
  it.each(['0','-1','1.001','abc','1e3'])('rejects invalid amount %s',amount=>expect(validate([line(amount)]).length).toBeGreaterThan(0));
  it('accepts multiple lines and retains cents',()=>{expect(validate([line('10.10','A'),line('0.20','B')])).toEqual([]);expect(cents('10.10')+cents('0.20')).toBe(1030);});
  it('rejects duplicate normalized references',()=>expect(validate([line('1',' A '),line('2','A')])).toContain('Line 2: duplicate external reference.'));
});
