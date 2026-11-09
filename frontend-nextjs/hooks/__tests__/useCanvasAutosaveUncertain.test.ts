import {renderHook,act} from '@testing-library/react';
import {useCanvasAutosave} from '../useCanvasAutosave';
afterEach(()=>jest.useRealTimers());
it('does not redispatch an explicitly non-retryable save through timer, manual flush, edits or unmount',async()=>{
 jest.useFakeTimers();const error=Object.assign(new Error('Not confirmed'),{retryable:false});const save=jest.fn().mockRejectedValue(error);
 const {result,unmount}=renderHook(()=>useCanvasAutosave({save,delayMs:10,maxRetries:2}));
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 expect(save).toHaveBeenCalledTimes(1);expect((result.current as any).blocked).toBe(true);
 await act(async()=>{await result.current.flush({force:true});jest.advanceTimersByTime(10000);});
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10000);});
 act(()=>window.dispatchEvent(new Event('beforeunload')));unmount();
 expect(save).toHaveBeenCalledTimes(1);
});
it('only an authoritative reset releases the block for a subsequent edit',async()=>{
 jest.useFakeTimers();const save=jest.fn().mockRejectedValue(Object.assign(new Error('Unconfirmed'),{retryable:false}));
 const {result}=renderHook(()=>useCanvasAutosave({save,delayMs:10}));
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 expect((result.current as any).blocked).toBe(true);
 save.mockResolvedValue(true);act(()=>result.current.reset());act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 expect(save).toHaveBeenCalledTimes(2);expect(result.current.status).toBe('saved');expect((result.current as any).blocked).toBe(false);
});
it('reports failed flush so a dependent chat dispatch cannot assume persistence',async()=>{
 const {result}=renderHook(()=>useCanvasAutosave({save:jest.fn().mockResolvedValue(false),maxRetries:0}));
 let success:any;await act(async()=>{success=await result.current.flush({force:true});});expect(success).toBe(false);
});
it('saves a new authoritative generation after an older in-flight save settles',async()=>{
 jest.useFakeTimers();let finish!:(v:boolean)=>void;
 const save=jest.fn().mockImplementationOnce(()=>new Promise<boolean>(resolve=>{finish=resolve;})).mockResolvedValue(true);
 const {result}=renderHook(()=>useCanvasAutosave({save,delayMs:10}));
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 expect(save).toHaveBeenCalledTimes(1);
 act(()=>result.current.reset());act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 await act(async()=>{finish(true);});await act(async()=>{jest.advanceTimersByTime(100);});
 expect(save).toHaveBeenCalledTimes(2);expect(result.current.status).toBe('saved');
});

it('does not mark later keystrokes saved by an older in-flight receipt',async()=>{
 jest.useFakeTimers();let finish!:(v:boolean)=>void;
 const save=jest.fn().mockImplementationOnce(()=>new Promise<boolean>(resolve=>{finish=resolve;})).mockResolvedValue(true);
 const {result}=renderHook(()=>useCanvasAutosave({save,delayMs:10}));
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 act(()=>result.current.schedule());await act(async()=>{jest.advanceTimersByTime(10);});
 await act(async()=>{finish(true);});expect(result.current.status).toBe('pending');
 await act(async()=>{jest.advanceTimersByTime(10);});expect(save).toHaveBeenCalledTimes(2);expect(result.current.status).toBe('saved');
});
