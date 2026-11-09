import React from 'react';
import {render,screen,fireEvent,act,cleanup} from '@testing-library/react';
import '@testing-library/jest-dom';
const mockReplace=jest.fn();
jest.mock('next/router',()=>({useRouter:()=>({pathname:'/dashboard',push:jest.fn(),replace:mockReplace})}));
jest.mock('next-auth/react',()=>({useSession:()=>({data:null,status:'unauthenticated'}),signOut:jest.fn().mockResolvedValue(undefined)}));
jest.mock('@/hooks/useActionProposals',()=>({useActionProposals:()=>({pendingCount:null,isPending:false,isError:false})}));
jest.mock('@/lib/user-role',()=>({useUserRole:()=>({role:'member',level:3,isSupervisor:false,isAdmin:false,loading:false}),ADMIN_MIN_LEVEL:5,SUPERVISOR_MIN_LEVEL:4}));
jest.mock('@/lib/product-profile',()=>({useProductProfile:()=>({isCapabilityEnabled:()=>true})}));
import Sidebar from '@/components/layout/Sidebar';
import {signOut} from 'next-auth/react';
const originalBase=process.env.NEXT_PUBLIC_API_URL;
let warn:jest.SpyInstance;
beforeEach(()=>{
 jest.clearAllMocks();localStorage.clear();localStorage.setItem('auth_token','old-fixture-bearer');localStorage.setItem('token','old-fixture-bearer');localStorage.setItem('access_token','old-fixture-bearer');localStorage.setItem('user_email','fixture@example.invalid');
 process.env.NEXT_PUBLIC_API_URL='http://owned-backend.invalid';global.fetch=jest.fn();warn=jest.spyOn(console,'warn').mockImplementation(()=>{});
});
afterEach(()=>{cleanup();warn.mockRestore();jest.useRealTimers();localStorage.clear();if(originalBase===undefined)delete process.env.NEXT_PUBLIC_API_URL;else process.env.NEXT_PUBLIC_API_URL=originalBase;});
it('releases local sign-out after a bounded stalled backend notification',async()=>{
 jest.useFakeTimers();(fetch as jest.Mock).mockImplementation((_url,options)=>new Promise((_resolve,reject)=>options.signal?.addEventListener('abort',()=>reject(new Error('synthetic transport failure')))));
 render(<Sidebar/>);fireEvent.click(screen.getByRole('button',{name:'Sign out'}));
 await act(async()=>{await jest.advanceTimersByTimeAsync(5001);});
 expect(localStorage.getItem('auth_token')).toBeNull();expect(localStorage.getItem('access_token')).toBeNull();expect(localStorage.getItem('user_email')).toBeNull();
 expect(localStorage.getItem('atom_explicit_logout')).toBe('1');expect(signOut).toHaveBeenCalledTimes(1);expect(fetch).toHaveBeenCalledTimes(1);
});
it('does not dispatch duplicate logout writes while the first notification is pending',async()=>{
 let finish!:(value:any)=>void;(fetch as jest.Mock).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 render(<Sidebar/>);const button=screen.getByRole('button',{name:'Sign out'});fireEvent.click(button);fireEvent.click(button);
 expect(fetch).toHaveBeenCalledTimes(1);
 await act(async()=>{finish({ok:true,status:200,json:async()=>({success:true,verification:{status:'verified'}})});});
 expect(signOut).toHaveBeenCalledTimes(1);
});
it('does not erase a newer signed-in session after an old logout notification resolves',async()=>{
 let finish!:(value:any)=>void;(fetch as jest.Mock).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 render(<Sidebar/>);fireEvent.click(screen.getByRole('button',{name:'Sign out'}));
 localStorage.setItem('auth_token','new-fixture-bearer');localStorage.setItem('token','new-fixture-bearer');localStorage.setItem('access_token','new-fixture-bearer');localStorage.setItem('user_email','new@example.invalid');
 await act(async()=>{finish({ok:true,status:200,json:async()=>({success:true,verification:{status:'verified'}})});});
 expect(localStorage.getItem('auth_token')).toBe('new-fixture-bearer');expect(localStorage.getItem('user_email')).toBe('new@example.invalid');expect(signOut).not.toHaveBeenCalled();
});

it('does not clear session material or dispatch a framework logout after unmount',async()=>{
 let finish!:(value:any)=>void;(fetch as jest.Mock).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const view=render(<Sidebar/>);fireEvent.click(screen.getByRole('button',{name:'Sign out'}));view.unmount();
 await act(async()=>{finish({ok:true,status:200,json:async()=>({success:true,verification:{status:'verified'}})});});
 expect(localStorage.getItem('auth_token')).toBe('old-fixture-bearer');expect(signOut).not.toHaveBeenCalled();
});
it('clears the original local session on an explicitly unverified server response without retry',async()=>{
 (fetch as jest.Mock).mockResolvedValue({ok:false,status:503,json:async()=>({success:false,detail:'old-fixture-bearer',verification:{status:'unavailable'}})});
 render(<Sidebar/>);await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Sign out'}));});
 expect(localStorage.getItem('auth_token')).toBeNull();expect(signOut).toHaveBeenCalledTimes(1);expect(fetch).toHaveBeenCalledTimes(1);
 expect(JSON.stringify(warn.mock.calls)).not.toContain('old-fixture-bearer');
});

it('reaches sign-in without waiting for an unresponsive framework logout and forbids its late redirect',async()=>{
 (signOut as jest.Mock).mockImplementationOnce(()=>new Promise(()=>{}));
 (fetch as jest.Mock).mockResolvedValue({ok:true,status:200,json:async()=>({success:true,verification:{status:'verified'}})});
 render(<Sidebar/>);await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Sign out'}));});
 expect(localStorage.getItem('auth_token')).toBeNull();
 expect(signOut).toHaveBeenCalledWith({callbackUrl:'/auth/signin',redirect:false});
 expect(mockReplace).toHaveBeenCalledWith('/auth/signin');
});
