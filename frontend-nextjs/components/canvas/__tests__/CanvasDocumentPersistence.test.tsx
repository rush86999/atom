import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import '@testing-library/jest-dom';
import {rest} from 'msw';
import {server} from '@/tests/mocks/server';
import {CanvasPanel} from '../CanvasPanel';
import {CanvasHost} from '@/components/chat/canvas-host';
jest.mock('next/router',()=>({useRouter:()=>({push:jest.fn()})}));
jest.mock('@monaco-editor/react',()=>({__esModule:true,default:({value,onChange}:any)=><textarea aria-label="Document editor" value={value} onChange={e=>onChange?.(e.target.value)}/> }));

describe.each([['standalone page',CanvasPanel],['chat host',CanvasHost]] as const)('%s native text persistence',(_surface,Surface)=>{
 function openDocument(data:any, component="document"){return render(<Surface lastMessage={{type:'canvas:update',data:{action:'present',id:'ordinary-document',component,title:'Ordinary document',data,version:1}}}/>)}
 let puts:any[];let artifacts:any[];
 beforeEach(()=>{puts=[];artifacts=[];delete (window as any).atom;server.use(
  rest.put('*/api/canvas/:id',async(req,res,ctx)=>{puts.push({id:req.params.id,body:req.body});return res(ctx.json({success:true,canvas_id:req.params.id,verification:{status:'verified',effect:'committed'}}));}),
  rest.post('/api/artifacts/update',async(req,res,ctx)=>{artifacts.push(req.body);return res(ctx.json({id:'ordinary-document',version:2}));})
 );});
 it.each(['document','markdown','code'])('shows an empty %s body rather than its JSON storage envelope',(component)=>{
  openDocument({content:''},component);expect(screen.getByRole('textbox',{name:'Document editor'})).toHaveValue('');
 });
 it.each(['document','markdown','code'])('saves the exact %s body into the original canvas audit and preserves envelope metadata',async(component)=>{
  openDocument({content:'Original body',source_record:'retained-source',qualifiers:{reviewed:true}},component);
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Reviewed quantity remains 4.'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));
  expect(puts[0]).toEqual({id:'ordinary-document',body:{content:'Reviewed quantity remains 4.',source_record:'retained-source',qualifiers:{reviewed:true}}});
  expect(artifacts).toHaveLength(0);
 });
 it.each(['document','markdown','code'])('does not certify a refused native %s save via an unrelated legacy artifact',async(component)=>{
  server.use(rest.put('*/api/canvas/:id',async(req,res,ctx)=>{puts.push(req.body);return res(ctx.status(503),ctx.json({verification:{effect:'unknown'},replay:'do_not_repeat'}));}));
  openDocument({content:'Original'},component);
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Unconfirmed edit'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));
  expect(artifacts).toHaveLength(0);
  expect(screen.getByText('Save Changes')).toBeInTheDocument();
 });
 it.each(['document','markdown','code'])('preserves legacy plain-string %s audit content',async(component)=>{
  openDocument('Original legacy text',component);
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Confirmed plain text'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));
  expect(puts[0].body).toBe('Confirmed plain text');
  expect(artifacts).toHaveLength(0);
 });



 it('keeps an ordinary clean type change available without a duplicate save',async()=>{
  const requests:string[]=[];
  server.use(rest.put('*/api/canvas/:id',async(req,res,ctx)=>{requests.push(req.url.toString());return res(ctx.json({success:true,canvas_id:req.params.id,verification:{status:'verified',effect:'committed'}}));}));
  openDocument({content:'Retained text'});
  fireEvent.click(screen.getByRole('button',{name:'document',exact:true}));
  fireEvent.click(screen.getByRole('option',{name:'Markdown',exact:true}));
  await waitFor(()=>expect(requests).toHaveLength(1));
  expect(new URL(requests[0]).searchParams.get('retype')).toBe('true');
  expect(await screen.findByRole('button',{name:'markdown',exact:true})).toBeEnabled();
 });
 it('cannot clear an uncertain save through an already-open type menu',async()=>{
  let attempts=0;
  server.use(rest.put('*/api/canvas/:id',async(req,res,ctx)=>{attempts++;return res(ctx.status(503),ctx.json({replay:'do_not_repeat',verification:{effect:'unknown'}}));}));
  openDocument({content:'Original'});
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Unconfirmed body'}});
  fireEvent.click(screen.getByRole('button',{name:'document',exact:true}));
  expect(screen.getByRole('listbox')).toBeInTheDocument();
  fireEvent.click(screen.getByText('Save Changes'));
  await screen.findByText('Save not confirmed. Check version history before retrying.');
  expect(screen.getByRole('button',{name:'document',exact:true})).toBeDisabled();
  expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  expect(attempts).toBe(1);
 });
 it.each(['docs','doc','generic','coding'])('uses the established %s registry alias for empty native text',async(component)=>{
  openDocument({content:''},component);
  expect(screen.getByRole('textbox',{name:'Document editor'})).toHaveValue('');
  fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Alias body'}});
  fireEvent.click(screen.getByText('Save Changes'));
  await waitFor(()=>expect(puts).toHaveLength(1));expect(puts[0].body).toEqual({content:'Alias body'});
 });

});

it('blocks dependent co-editor work when the native document save is not confirmed',async()=>{
 const register=jest.fn();let writes=0;
 server.use(rest.put('*/api/canvas/:id',async(req,res,ctx)=>{writes++;return res(ctx.status(503),ctx.json({replay:'do_not_repeat',verification:{effect:'unknown'}}));}));
 render(<CanvasPanel registerFlushBeforeSend={register} lastMessage={{type:'canvas:update',data:{action:'present',id:'dependent-canvas',component:'document',data:{content:'Before'}}}}/>);
 fireEvent.change(screen.getByRole('textbox',{name:'Document editor'}),{target:{value:'Must be saved before agent plans'}});
 await expect(register.mock.calls[register.mock.calls.length-1][0]()).rejects.toThrow('save is not confirmed');
 expect(writes).toBe(1);expect(await screen.findByText('Save not confirmed. Check version history before retrying.')).toBeInTheDocument();
 expect(screen.getByText('Save Changes').closest('button')).toBeDisabled();
});
