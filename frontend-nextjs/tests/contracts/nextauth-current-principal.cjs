// Real installed NextAuth JWT decode/session/getServerSession consumers.
// Only the canonical backend transport is doubled; no database/provider calls.
const {test,after}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const Module=require('node:module');const crypto=require('node:crypto');
const ts=require('typescript');const root=path.resolve(__dirname,'../..');
const originalResolve=Module._resolveFilename;const originalTs=require.extensions['.ts'];const originalFetch=global.fetch;
process.env.NODE_ENV='test';
process.env.NEXTAUTH_SECRET=crypto.randomBytes(32).toString('base64url');process.env.JWT_SECRET=process.env.NEXTAUTH_SECRET;
process.env.NEXTAUTH_URL='http://localhost:3000';process.env.NEXT_PUBLIC_API_URL='http://controlled-backend.invalid';
Module._resolveFilename=function(request,...args){if(request.startsWith('@/lib/'))request=path.join(root,request.slice(2));return originalResolve.call(this,request,...args);};
require.extensions['.ts']=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,filename);
const {getServerSession}=require('next-auth/next');const {encode}=require('next-auth/jwt');
const normal=require(path.join(root,'pages/api/auth/[...nextauth].ts')).authOptions;
const shared=require(path.join(root,'lib/auth.ts')).authOptions;
after(()=>{global.fetch=originalFetch;Module._resolveFilename=originalResolve;if(originalTs)require.extensions['.ts']=originalTs;else delete require.extensions['.ts'];});
const cached={id:'current-user',sub:'current-user',email:'old@example.invalid',name:'Old Name',role:'super_admin',workspace_id:'old-workspace',tenant_id:'old-tenant',scopes:['*'],is_admin:true,unrecognizedAuthority:true,permissions:['*'],admin_role:'super_admin',backendToken:'synthetic-backend-session'};
const current={id:'current-user',email:'current@example.invalid',first_name:'Current',last_name:'User',role:'member',workspace_id:'current-workspace',tenant_id:'current-tenant',status:'active'};
async function readSession(options,token=cached,existingCookie){
 const encrypted=existingCookie || await encode({token,secret:process.env.NEXTAUTH_SECRET,maxAge:60});
 const headers={};const errors=[];
 const opts={...options,logger:{error:(...args)=>errors.push(args),warn:()=>{},debug:()=>{}}};
 const cookie=options.cookies?.sessionToken?.name||'next-auth.session-token';
 const req={cookies:{[cookie]:encrypted},headers:{cookie:`${cookie}=${encrypted}`}};
 const res={getHeader:(name)=>headers[name],setHeader:(name,value)=>{headers[name]=value;}};
 const session=await getServerSession(req,res,opts);return {session,headers,errors};
}
for(const [name,options] of [['normal',normal],['shared',shared]]){
 test(`${name}: revoked backend bearer cannot certify a server-side web session`,async()=>{
  let calls=0;global.fetch=async()=>{calls++;return new Response('{}',{status:401,headers:{'Content-Type':'application/json'}});};
  const {session,headers}=await readSession(options);assert.equal(session,null);assert.equal(calls,1);assert.match(JSON.stringify(headers),/next-auth.session-token/);
 });
 test(`${name}: a cookie without a backend generation requires fresh login`,async()=>{
  let calls=0;global.fetch=async()=>{calls++;throw new Error('must not dispatch');};
  const {backendToken,...legacy}=cached;const {session}=await readSession(options,legacy);assert.equal(session,null);assert.equal(calls,0);
 });
 test(`${name}: current canonical role and workspace replace cached authority`,async()=>{
  let calls=0;global.fetch=async(url,opts)=>{calls++;assert.match(url,/\/api\/auth\/me$/);assert.equal(opts.headers.Authorization,'Bearer synthetic-backend-session');return new Response(JSON.stringify(current),{status:200});};
  const {session}=await readSession(options);assert.equal(calls,1);assert.equal(session.user.id,current.id);assert.equal(session.user.email,current.email);assert.equal(session.user.name,'Current User');assert.equal(session.user.tenant_id,current.tenant_id);assert.equal(session.user.role,'member');assert.equal(session.user.workspace_id,current.workspace_id);assert.equal(session.user.permissions,undefined);assert.equal(session.user.admin_role,undefined);
 });
 test(`${name}: a mismatched canonical subject is refused, not reassigned`,async()=>{
  global.fetch=async()=>new Response(JSON.stringify({...current,id:'another-user'}),{status:200});
  assert.equal((await readSession(options)).session,null);
 });
}
test('shared decoder uses the actual web-cookie secret, not an unrelated backend JWT_SECRET',async()=>{
 const original=process.env.JWT_SECRET;const file=require.resolve(path.join(root,'lib/auth.ts'));const entry=require.cache[file];
 try{
  process.env.JWT_SECRET=crypto.randomBytes(32).toString('base64url');delete require.cache[file];const fresh=require(file).authOptions;
  global.fetch=async()=>new Response(JSON.stringify(current),{status:200});
  assert.equal((await readSession(fresh)).session?.user.id,current.id);
 }finally{process.env.JWT_SECRET=original;require.cache[file]=entry;}
});
test('production web auth refuses to use a public development secret when configuration is missing',()=>{
 const names=['NODE_ENV','NEXTAUTH_SECRET','AUTH_SECRET','JWT_SECRET'];const old=Object.fromEntries(names.map(k=>[k,process.env[k]]));const file=require.resolve(path.join(root,'pages/api/auth/[...nextauth].ts'));const entry=require.cache[file];
 try{
  process.env.NODE_ENV='production';delete process.env.NEXTAUTH_SECRET;delete process.env.AUTH_SECRET;delete process.env.JWT_SECRET;delete require.cache[file];
  assert.throws(()=>require(file).authOptions.secret,/NEXTAUTH_SECRET/);
 }finally{for(const name of names){if(old[name]===undefined)delete process.env[name];else process.env[name]=old[name];}require.cache[file]=entry;}
});

for(const [name,options] of [['normal',normal],['shared',shared]]){
 for(const scope of [null,'','default']) test(`${name}: exact personal scope ${JSON.stringify(scope)} is preserved`,async()=>{
  global.fetch=async()=>new Response(JSON.stringify({...current,workspace_id:scope,tenant_id:scope}),{status:200});
  const {session}=await readSession(options);assert.equal(session.user.workspace_id,scope);assert.equal(session.user.tenant_id,scope);
 });
 for(const field of ['role','workspace_id','tenant_id']) test(`${name}: missing current ${field} cannot inherit cached authority`,async()=>{
  const principal={...current};delete principal[field];global.fetch=async()=>new Response(JSON.stringify(principal),{status:200});
  assert.equal((await readSession(options)).session,null);
 });
 test(`${name}: safe failure logs never echo transport credential material`,async()=>{
  global.fetch=async()=>{throw new Error('private transport '+cached.backendToken);};
  const result=await readSession(options);assert.equal(result.session,null);
  assert.equal(JSON.stringify(result.errors.map(args=>args.map(v=>v?.message||String(v)))).includes(cached.backendToken),false);
 });
 test(`${name}: inactive current identity never inherits a cached active session`,async()=>{
  global.fetch=async()=>new Response(JSON.stringify({...current,status:'inactive'}),{status:200});assert.equal((await readSession(options)).session,null);
 });
}
test('real SDK denies a principal when an actual HTTP identity body stalls past the single deadline',{timeout:15000},async()=>{
 const http=require('node:http');let requests=0;const server=http.createServer((req,res)=>{requests++;res.writeHead(200,{'Content-Type':'application/json'});res.write('{"id":');});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const original=process.env.NEXT_PUBLIC_API_URL;global.fetch=originalFetch;
 try{
  process.env.NEXT_PUBLIC_API_URL=`http://127.0.0.1:${server.address().port}`;const start=performance.now();const {session}=await readSession(normal);
  assert.equal(session,null);assert.equal(requests,1);assert.ok(performance.now()-start<12000);
 }finally{process.env.NEXT_PUBLIC_API_URL=original;server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});
for(const [name,options] of [['normal',normal],['shared',shared]]) test(`${name}: an explicit unsuccessful identity result cannot certify cached authority`,async()=>{
 global.fetch=async()=>new Response(JSON.stringify({...current,success:false}),{status:200});
 assert.equal((await readSession(options)).session,null);
});

for(const [name,options] of [['normal',normal],['shared',shared]]) test(`${name}: unavailable current authority refuses without destroying the recoverable cookie`,async()=>{
 global.fetch=async()=>new Response('{}',{status:503});const first=await readSession(options);assert.equal(first.session,null);
 const cookies=first.headers['Set-Cookie']||[];assert.equal(cookies.some(cookie=>cookie.includes('Max-Age=0')),false);
 const cookie=cookies.find(value=>value.startsWith('next-auth.session-token='));assert.ok(cookie,'recoverable cookie retained');const value=cookie.split(';')[0].slice('next-auth.session-token='.length);assert.ok(value);
 global.fetch=async()=>new Response(JSON.stringify(current),{status:200});
 const second=await readSession(options,cached,value);assert.equal(second.session.user.id,current.id);assert.equal(second.session.user.role,'member');
});

for (const [name,options] of [['normal',normal],['shared',shared]]) test(`${name}: unknown cached authority cannot survive a current-principal projection`,async()=>{
 global.fetch=async()=>new Response(JSON.stringify(current),{status:200});
 const {session}=await readSession(options);
 assert.ok(session);for(const key of ['scopes','is_admin','unrecognizedAuthority','permissions','admin_role'])assert.equal(session.user[key],undefined);
 const {projectCurrentBackendSession}=require(path.join(root,'lib/backend-current-session.ts'));
 const token={...cached};const projected=await projectCurrentBackendSession({expires:'later',user:{...cached}},token,()=>process.env.NEXT_PUBLIC_API_URL);
 assert.ok(projected);for(const key of ['scopes','is_admin','unrecognizedAuthority','permissions','admin_role']){assert.equal(token[key],undefined);assert.equal(projected.user[key],undefined);}
});

for(const mode of ['test','development','production'])test(`missing web signing secret refuses in ${mode}`,()=>{
 const {resolveWebAuthSecret}=require(path.join(root,'lib/web-auth-config.ts'));const old=process.env.NEXTAUTH_SECRET;const modeBefore=process.env.NODE_ENV;
 try{process.env.NODE_ENV=mode;delete process.env.NEXTAUTH_SECRET;assert.throws(resolveWebAuthSecret,/NEXTAUTH_SECRET/);}finally{process.env.NEXTAUTH_SECRET=old;process.env.NODE_ENV=modeBefore;}
});
for(const value of [undefined,'/relative','file:///tmp/authority','http://user:password@localhost:8000','http://localhost:8000/?secret=value','http://localhost:8000/#fragment'])test('invalid or absent auth backend never substitutes localhost',()=>{
 const {resolveWebAuthBackend}=require(path.join(root,'lib/web-auth-config.ts'));const names=['NEXT_PUBLIC_API_URL','API_BASE_URL','PYTHON_BACKEND_URL'];const old=Object.fromEntries(names.map(k=>[k,process.env[k]]));
 try{for(const k of names)delete process.env[k];if(value!==undefined)process.env.NEXT_PUBLIC_API_URL=value;assert.throws(resolveWebAuthBackend,/WEB_AUTH_BACKEND/);}finally{for(const k of names){if(old[k]===undefined)delete process.env[k];else process.env[k]=old[k];}}
});

test('server auth uses configured private authority before browser URL and normalizes whitespace',()=>{
 const {resolveWebAuthBackend}=require(path.join(root,'lib/web-auth-config.ts'));const old=process.env.API_BASE_URL;
 try{process.env.API_BASE_URL=' http://127.0.0.1:18000/prefix/// ';assert.equal(resolveWebAuthBackend(),'http://127.0.0.1:18000/prefix');}finally{if(old===undefined)delete process.env.API_BASE_URL;else process.env.API_BASE_URL=old;}
});
