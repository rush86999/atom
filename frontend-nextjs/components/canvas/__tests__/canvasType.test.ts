/**
 * canvasType conversion tests (components/canvas/canvasType.ts)
 *
 * The manual type switcher's conversion heuristics: which types offer the
 * switch, markdown table ⇄ sheet rows, text preservation across text-like
 * types, and the email→document subject heading. Regression guard for the
 * `"|" in string` crash that broke every markdown→sheet conversion.
 */
import {
    CANVAS_TYPE_OPTIONS,
    isTypeSwitchable,
    switchCanvasType,
} from '@/components/canvas/canvasType';

describe('isTypeSwitchable', () => {
    it('offers the switch for every text-like canvas type', () => {
        for (const opt of CANVAS_TYPE_OPTIONS) {
            expect(isTypeSwitchable(opt.value)).toBe(true);
        }
    });

    it('renders a plain badge for specialized canvases', () => {
        for (const component of [
            'office_excel', 'office_word', 'office_pptx', 'form',
            'snapshot', 'browser_view', 'status_panel', 'eval', undefined, null,
        ]) {
            expect(isTypeSwitchable(component)).toBe(false);
        }
    });
});

describe('switchCanvasType', () => {
    it('parses a markdown table into sheet rows', () => {
        const table = '| Feature | Status |\n| --- | --- |\n| Retype | Pinned |\n| Menu | Open |';
        const conv = switchCanvasType('sheet', {
            component: 'markdown',
            data: table,
            text: table,
        });
        expect(conv.sheet).toEqual([
            ['Feature', 'Status'],
            ['Retype', 'Pinned'],
            ['Menu', 'Open'],
        ]);
    });

    it('falls back to one row per non-empty line when there is no table', () => {
        const conv = switchCanvasType('sheet', {
            component: 'markdown',
            data: 'alpha\n\nbeta',
            text: 'alpha\n\nbeta',
        });
        expect(conv.sheet).toEqual([['alpha'], ['beta']]);
    });

    it('preserves text verbatim across text-like types', () => {
        const src = { component: 'code', data: 'const x = 1;', text: 'const x = 1;' };
        expect(switchCanvasType('markdown', src).text).toBe('const x = 1;');
        expect(switchCanvasType('code', src).text).toBe('const x = 1;');
    });

    it('keeps the email subject as the document heading when retyping the composer', () => {
        const conv = switchCanvasType('document', {
            component: 'email',
            data: { to: 'a@b.c', subject: 'Q3 report', body: 'Numbers attached.' },
            text: 'Numbers attached.',
            email: { to: 'a@b.c', subject: 'Q3 report' },
        });
        expect(conv.text).toBe('# Q3 report\n\nNumbers attached.');
    });

    it('rides To/Cc/Subject along into a switched email composer', () => {
        const conv = switchCanvasType('email', {
            component: 'markdown',
            data: 'See below.',
            text: 'See below.',
            email: { to: 'x@y.z', cc: 'q@r.s', subject: 'Follow-up' },
        });
        expect(conv.email).toEqual({ to: 'x@y.z', cc: 'q@r.s', subject: 'Follow-up' });
        expect(conv.data.body).toBe('See below.');
    });
});
