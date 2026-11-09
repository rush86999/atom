import { createBackendCredentialsAuthorize } from '@/lib/backend-credentials';
const credentials = { email:'fixture@example.invalid',password:'synthetic-private-marker',totp_code:'synthetic-code' };
const response = (body:any,status=200) => ({ok:status===200,status,json:async()=>body});
let warn:jest.SpyInstance;
beforeEach(()=>{global.fetch=jest.fn();warn=jest.spyOn(console,'warn').mockImplementation(()=>{});});
afterEach(()=>{warn.mockRestore();jest.useRealTimers();});
it.each([undefined,{}, {email:credentials.email}, {password:credentials.password}])('does not dispatch missing credentials %j',async c=>{
 expect(await createBackendCredentialsAuthorize(()=>'/backend')(c)).toBeNull();expect(fetch).not.toHaveBeenCalled();
});
it.each([[{two_factor_required:true},200,'2FA_REQUIRED'],[{detail:'Invalid 2FA code'},401,'INVALID_2FA_CODE']])('keeps the backend challenge without issuing /me',async(body,status,code)=>{
 (fetch as jest.Mock).mockResolvedValue(response(body,status as number));
 await expect(createBackendCredentialsAuthorize(()=>'/backend')(credentials)).rejects.toThrow(code as string);
 expect(fetch).toHaveBeenCalledTimes(1);expect(warn).not.toHaveBeenCalled();
});
it('does not trust a challenge-shaped error response as a successful login',async()=>{
 (fetch as jest.Mock).mockResolvedValue(response({two_factor_required:true},500));
 expect(await createBackendCredentialsAuthorize(()=>'/backend')(credentials)).toBeNull();expect(fetch).toHaveBeenCalledTimes(1);
});
it('forwards an existing 2FA field once and obtains identity only from that issued bearer',async()=>{
 (fetch as jest.Mock).mockResolvedValueOnce(response({access_token:'fixture-bearer'})).mockResolvedValueOnce(response({id:'canonical',email:'canonical@example.invalid',status:'active',role:'member',workspace_id:'workspace'}));
 const user=await createBackendCredentialsAuthorize(()=>'/backend/')(credentials);
 expect(user).toMatchObject({id:'canonical',email:'canonical@example.invalid',role:'member',workspace_id:'workspace',token:'fixture-bearer',access_token:'fixture-bearer'});
 expect(JSON.parse((fetch as jest.Mock).mock.calls[0][1].body)).toEqual({username:credentials.email,password:credentials.password,totp_code:credentials.totp_code});
 expect(fetch).toHaveBeenCalledTimes(2);
});
it('bounds an unresponsive dispatch, aborts once and never retries credentials',async()=>{
 jest.useFakeTimers();(fetch as jest.Mock).mockImplementation((_url,options)=>new Promise((_resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error(credentials.password)))));
 const pending=createBackendCredentialsAuthorize(()=>'/backend')(credentials);
 await jest.advanceTimersByTimeAsync(10000);expect(await pending).toBeNull();expect(fetch).toHaveBeenCalledTimes(1);expect(jest.getTimerCount()).toBe(0);
 expect(JSON.stringify(warn.mock.calls)).not.toContain(credentials.password);
});
it('does not adopt a login body arriving after the single deadline',async()=>{
 jest.useFakeTimers();let resolveBody!:(body:any)=>void;
 (fetch as jest.Mock).mockResolvedValue({ok:true,json:()=>new Promise(resolve=>{resolveBody=resolve;})});
 const pending=createBackendCredentialsAuthorize(()=>'/backend')(credentials);await Promise.resolve();
 await jest.advanceTimersByTimeAsync(10000);resolveBody({access_token:'fixture-bearer'});
 expect(await pending).toBeNull();expect(fetch).toHaveBeenCalledTimes(1);expect(jest.getTimerCount()).toBe(0);
});

it('forbids credential and bearer forwarding through redirects',async()=>{
 (fetch as jest.Mock).mockResolvedValueOnce(response({access_token:'fixture-bearer'})).mockResolvedValueOnce(response({id:'canonical',email:'canonical@example.invalid',status:'active'}));
 await createBackendCredentialsAuthorize(()=>'/backend')(credentials);
 expect((fetch as jest.Mock).mock.calls).toHaveLength(2);
 for(const call of (fetch as jest.Mock).mock.calls) expect(call[1].redirect).toBe('error');
});
it('cancels the refused identity response without leaving an unbounded body',async()=>{
 (fetch as jest.Mock).mockResolvedValueOnce(response({access_token:'fixture-bearer'})).mockResolvedValueOnce({ok:false,status:403,json:jest.fn()});
 expect(await createBackendCredentialsAuthorize(()=>'/backend')(credentials)).toBeNull();
 expect((fetch as jest.Mock).mock.calls[1][1].signal.aborted).toBe(true);
});
