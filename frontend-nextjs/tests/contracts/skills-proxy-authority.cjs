// Real installed NextAuth encrypted-cookie decoder and actual public handlers.
// Only backend transport and the obsolete client getSession are controlled.
const {test,after}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),Module=require('node:module'),crypto=require('node:crypto'),ts=require('typescript');
const root=path.resolve(__dirname,'../..');const resolve=Module._resolveFilename,load=Module._load,extension=require.extensions['.ts'],fetchBefore=global.fetch;
process.env.NODE_ENV='test';process.env.NEXTAUTH_SECRET=crypto.randomBytes(48).toString('base64url');process.env.NEXTAUTH_URL='http://localhost:3000';process.env.API_BASE_URL='http://controlled-backend.invalid';process.env.BACKEND_URL='http://controlled-backend.invalid';process.env.BACKEND_API_URL='http://controlled-backend.invalid';
Module._resolveFilename=function(request,...args){if(request.startsWith('@/lib/'))request=path.join(root,request.slice(2));return resolve.call(this,request,...args);};
Module._load=function(request,...args){if(request==='next-auth/react')return {getSession:async()=>null};return load.call(this,request,...args);};
require.extensions['.ts']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,filename);
const {encode}=require('next-auth/jwt');const handler=require(path.join(root,'pages/api/skills/list.ts')).default;
after(()=>{global.fetch=fetchBefore;Module._resolveFilename=resolve;Module._load=load;if(extension)require.extensions['.ts']=extension;else delete require.extensions['.ts'];});
async function invoke({token,authorization,query={},rawCookie}={}){
 const cookies={};if(token)cookies['next-auth.session-token']=await encode({token,secret:process.env.NEXTAUTH_SECRET,maxAge:60});
 if(rawCookie)cookies['next-auth.session-token']=rawCookie;
 const headers={cookie:Object.entries(cookies).map(([k,v])=>k+'='+v).join(';')};if(authorization!==undefined)headers.authorization=authorization;
 const req={method:'GET',headers,cookies,query};const result={status:200,headers:{},body:undefined};
 const res={setHeader:(k,v)=>{result.headers[k.toLowerCase()]=v;},status(n){result.status=n;return this;},json(body){result.body=body;return this;}};
 await handler(req,res);return result;
}
const ready={success:true,data:{skills:[{skill_id:'skill-one'}],total:1}};
test('actual encrypted web cookie forwards only its exact backend generation',async()=>{
 let auth;global.fetch=async(url,init)=>{auth=init.headers.Authorization;return Response.json(ready);};
 const result=await invoke({token:{id:'person-a',backendToken:'controlled-backend-generation'}});
 assert.equal(auth,'Bearer controlled-backend-generation');assert.equal(result.status,200);assert.deepEqual(result.body,ready);assert.match(result.headers['cache-control'],/private.*no-store/);
});
test('upstream refusal never becomes success with zero skills',async()=>{
 global.fetch=async()=>Response.json({detail:'not authorized'},{status:401});const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,401);assert.notEqual(result.body?.success,true);
});
test('upstream unavailable never becomes a successful empty catalogue',async()=>{
 global.fetch=async()=>{throw Error('private-transport-diagnostic');};const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,503);assert.notEqual(result.body?.success,true);assert.doesNotMatch(JSON.stringify(result),/private-transport-diagnostic/);
});
test('missing credentials refuse before dispatch',async()=>{
 let calls=0;global.fetch=async()=>{calls++;return Response.json(ready);};const result=await invoke();assert.equal(result.status,401);assert.equal(calls,0);
});
test('invalid explicit authority cannot borrow an encrypted cookie',async()=>{
 let calls=0;global.fetch=async()=>{calls++;return Response.json(ready);};const result=await invoke({authorization:'Basic invalid',token:{backendToken:'another-generation'}});assert.equal(result.status,401);assert.equal(calls,0);
});
test('an actual verified empty catalogue remains successful',async()=>{
 const empty={success:true,data:{skills:[],total:0}};global.fetch=async()=>Response.json(empty);const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,200);assert.deepEqual(result.body,empty);assert.match(result.headers['cache-control'],/private.*no-store/);
});
test('a malformed successful catalogue is not presented as loaded',async()=>{
 global.fetch=async()=>Response.json({success:true,data:{skills:'invalid',total:0}});const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,502);assert.notEqual(result.body?.success,true);
});
test('raw error body is never reflected to caller',async()=>{
 global.fetch=async()=>new Response('PRIVATE_BACKEND_DIAGNOSTIC',{status:502,headers:{'Content-Type':'text/html'}});const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,503);assert.doesNotMatch(JSON.stringify(result),/PRIVATE_BACKEND_DIAGNOSTIC/);
});
test('query values are encoded and request transport refuses redirects',async()=>{
 let seen;global.fetch=async(url,init)=>{seen={url,init};return Response.json(ready);};await invoke({authorization:'Bearer controlled-bearer',query:{status:'Active & current',limit:'3'}});assert.equal(new URL(seen.url).searchParams.get('status'),'Active & current');assert.equal(seen.init.redirect,'error');assert.equal(seen.init.cache,'no-store');
});

test('tampered encrypted cookie is an authentication refusal, not an outage',async()=>{
 let calls=0;global.fetch=async()=>{calls++;return Response.json(ready);};const result=await invoke({rawCookie:'invalid-encrypted-cookie'});assert.equal(result.status,401);assert.equal(calls,0);
});
test('explicit refused bearer never borrows another valid cookie',async()=>{
 let calls=0;global.fetch=async(url,init)=>{calls++;assert.equal(init.headers.Authorization,'Bearer refused-generation');return Response.json({detail:'invalid'},{status:401});};
 const result=await invoke({authorization:'Bearer refused-generation',token:{backendToken:'valid-other-generation'}});assert.equal(result.status,401);assert.equal(calls,1);
});
test('ordinary id query filter remains an encoded query value',async()=>{
 let url;global.fetch=async(target)=>{url=target;return Response.json(ready);};await invoke({authorization:'Bearer controlled-bearer',query:{id:'opaque-filter'}});assert.equal(new URL(url).searchParams.get('id'),'opaque-filter');
});
test('shared transport preserves a confirmed no-content response without parsing or replay',async()=>{
 const {forwardBackendApi}=require(path.join(root,'lib/backend-api-proxy.ts'));let calls=0,ended=false,status;
 global.fetch=async()=>{calls++;return new Response(null,{status:204});};
 await forwardBackendApi({method:'DELETE',headers:{authorization:'Bearer controlled-bearer'},cookies:{},query:{}},{setHeader(){},status(n){status=n;return this;},end(){ended=true;},json(){assert.fail('no invented JSON success');}},'/api/v1/tasks/current',['DELETE']);
 assert.equal(status,204);assert.equal(ended,true);assert.equal(calls,1);
});
test('non-JSON refusal retains the backend status without its diagnostics',async()=>{
 global.fetch=async()=>new Response('PRIVATE_REFUSAL_DETAIL',{status:403});const result=await invoke({authorization:'Bearer controlled-bearer'});assert.equal(result.status,403);assert.doesNotMatch(JSON.stringify(result),/PRIVATE_REFUSAL_DETAIL/);
});
