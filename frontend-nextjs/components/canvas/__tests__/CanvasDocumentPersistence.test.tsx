import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import '@testing-library/jest-dom';
import {rest} from 'msw';
import {server} from '@/tests/mocks/server';
import {CanvasPanel} from '../CanvasPanel';
jest.mock('@monaco-editor/react',()=>({__esModule:true,default:({value,onChange}:any)=><textarea aria-label="Document editor" value={value} onChange={e=>onChange?.(e.target.value)}/> }));

function openDocument(data:any){return render(<CanvasPanel lastMessage={{type:'canvas:update',data:{action:'present',id:'ordinary-document',component:'document',title:'Ordinary document',data,version:1}}}/>)}
describe('ordinary document native content persistence',()=>{
 let puts:any[];let artifacts:any[];
 beforeEach(()=>{puts=[];artifacts=[];delete (window as any).atom;server.use(
  rest.put('*/api/canvas/:id',async(req,res,ctx)=>{puts.push({id:req.params.id,body:req.body});return res(ctx.json({success:true,canvas_id:req.params.id}));}),
  rest.post('/api/artifacts/update',async(req,res,ctx)=>{artifacts.push(req.body);return res(ctx.json({id:'ordinary-document',version:2}));})
 );});
 it('shows an empty document body rather than its JSON storage envelope',()=>{
  openDocument({content:''});expect(screen.getByRole('textbox',{name:'Document editor'})).toHaveValue('');
 });
 it('saves the exact edited body into the original canvas audit and preserves envelope metadata',async()=>{
  openDocument({content:'Original body',source_record:'retained-source',qualifiers:{reviewed:true}});
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Reviewed quantity remains 4.'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));
  expect(puts[0]).toEqual({id:'ordinary-document',body:{content:'Reviewed quantity remains 4.',source_record:'retained-source',qualifiers:{reviewed:true}}});
  expect(artifacts).toHaveLength(0);
 });
 it('does not certify a refused native document save via an unrelated legacy artifact',async()=>{
  server.use(rest.put('*/api/canvas/:id',async(req,res,ctx)=>{puts.push(req.body);return res(ctx.status(503),ctx.json({verification:{effect:'unknown'},replay:'do_not_repeat'}));}));
  openDocument({content:'Original'});
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Unconfirmed edit'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));
  expect(artifacts).toHaveLength(0);
  expect(screen.getByText('Save Changes')).toBeInTheDocument();
 });
});
