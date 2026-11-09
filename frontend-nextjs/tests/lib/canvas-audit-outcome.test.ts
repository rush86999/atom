import {saveCanvasAudit} from '@/lib/canvasAuditSave';
import {apiClient} from '@/lib/api';
jest.mock('@/lib/api',()=>({apiClient:{put:jest.fn()}}));
const put=apiClient.put as jest.Mock;
beforeEach(()=>put.mockReset());
const verified={success:true,canvas_id:'exact-canvas',audit_id:'audit-exact',operation_id:'op-exact',verification:{status:'verified',effect:'committed'}};
it('accepts an exact verified receipt and disables generic transport retries',async()=>{
 put.mockResolvedValue({data:verified});expect(await saveCanvasAudit('exact-canvas','document','Title',{content:'Body'})).toBe(true);
 expect(put.mock.calls[0][2]).toMatchObject({retry:false});
});
it.each([
 {success:true,canvas_id:'exact-canvas'},
 {...verified,canvas_id:'other-canvas'},
 {...verified,verification:{status:'unavailable',effect:'committed'}},
 {...verified,success:false},
])('does not certify malformed, foreign or unverified transport success %#',async(data)=>{
 put.mockResolvedValue({data});await expect(saveCanvasAudit('exact-canvas','document','Title',{content:'Body'})).rejects.toMatchObject({retryable:false});
});
it('keeps a genuine legacy404 fallback distinct',async()=>{
 put.mockRejectedValue({response:{status:404}});expect(await saveCanvasAudit('exact-canvas','document','Title','Body')).toBe(false);
});
it.each([
 {code:'ERR_NETWORK',message:'sensitive sentinel'},
 {response:{status:503,data:{replay:'do_not_repeat',verification:{effect:'unknown'}}},message:'sensitive sentinel'},
 {response:{status:200,data:{verification:{status:'refuted',effect:'committed'}}},message:'sensitive sentinel'},
])('blocks uncertain failures without exposing raw details %#',async(error)=>{
 put.mockRejectedValue(error);
 try{await saveCanvasAudit('exact-canvas','document','Title','Body');throw new Error('expected failure');}
 catch(e:any){expect(e.retryable).toBe(false);expect(e.message).not.toContain('sensitive sentinel');}
});
it('a contradictory404 with unknown effect cannot authorize legacy fallback',async()=>{
 put.mockRejectedValue({response:{status:404,data:{replay:'do_not_repeat',verification:{effect:'unknown'},operation_id:'original-operation'}}});
 await expect(saveCanvasAudit('exact-canvas','document','Title','Body')).rejects.toMatchObject({retryable:false,operationId:'original-operation'});
});
it('does not coerce numeric or aliased identifiers into receipt identity',async()=>{
 put.mockRejectedValue({response:{status:503,data:{operation_id:77,auditId:'alias-only'}}});
 try{await saveCanvasAudit('exact-canvas','document','Title','Body');throw new Error('expected failure');}
 catch(e:any){expect(e.retryable).toBe(false);expect(e.operationId).toBeUndefined();expect(e.auditId).toBeUndefined();}
});

it.each(['Body', [['Part','Quantity'],['A',2]], {body:'Draft',to:'buyer@example.com'}])('confirms manual type writes through the same JSON and no-retry contract %#',async(content)=>{
 put.mockResolvedValue({data:verified});
 expect(await saveCanvasAudit('exact-canvas','markdown','Title',content,{retype:true})).toBe(true);
 expect(put).toHaveBeenCalledTimes(1);
 const [url,body,config]=put.mock.calls[0];
 expect(new URL(url,'http://localhost').searchParams.get('retype')).toBe('true');
 expect(body).toBe(JSON.stringify(content));
 expect(config).toMatchObject({retry:false,headers:{'Content-Type':'application/json'}});
});
it('does not mark ordinary edits as manual type changes',async()=>{
 put.mockResolvedValue({data:verified});await saveCanvasAudit('exact-canvas','document','Title','Body');
 expect(new URL(put.mock.calls[0][0],'http://localhost').searchParams.has('retype')).toBe(false);
});
