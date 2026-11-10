import React from 'react';
import {render,act,cleanup} from '@testing-library/react';
import SignIn from '@/pages/auth/signin';
import {getSession} from 'next-auth/react';
const mockPush=jest.fn();
jest.mock('next/router',()=>({useRouter:()=>({push:mockPush,query:{},pathname:'/auth/signin'})}));
jest.mock('next-auth/react',()=>({getSession:jest.fn(),signIn:jest.fn()}));
jest.mock('@/components/ui/use-toast',()=>({useToast:()=>({toast:jest.fn()})}));
jest.mock('@/lib/backendAuth',()=>({establishWebSession:jest.fn(),loginWithBackend:jest.fn(),persistBackendToken:jest.fn()}));
beforeEach(()=>{jest.clearAllMocks();localStorage.clear();});
afterEach(()=>{cleanup();localStorage.clear();});
it('does not revive a cached browser session after explicit local logout',async()=>{
 localStorage.setItem('atom_explicit_logout','1');(getSession as jest.Mock).mockResolvedValue({user:{id:'old'}});
 await act(async()=>{render(<SignIn/>);});
 expect(mockPush).not.toHaveBeenCalled();expect(localStorage.getItem('atom_explicit_logout')).toBe('1');
});
it('does not revive a session response that arrives after logout',async()=>{
 let finish!:(value:any)=>void;(getSession as jest.Mock).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 render(<SignIn/>);localStorage.setItem('atom_explicit_logout','1');
 await act(async()=>{finish({user:{id:'old'}});});
 expect(mockPush).not.toHaveBeenCalled();expect(localStorage.getItem('atom_explicit_logout')).toBe('1');
});
it('does not navigate from an unmounted sign-in generation',async()=>{
 let finish!:(value:any)=>void;(getSession as jest.Mock).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const view=render(<SignIn/>);view.unmount();await act(async()=>{finish({user:{id:'old'}});});
 expect(mockPush).not.toHaveBeenCalled();
});
