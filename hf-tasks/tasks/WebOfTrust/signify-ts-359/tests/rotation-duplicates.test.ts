import { assert, describe, it } from 'vitest';
import { rotate } from '../../src/keri/core/eventing.ts';

describe('rotate witness duplication checks', () => {
    it('rejects duplicate witness additions', () => {
        const args = {
            keys: ['key1'],
            pre: 'pre1',
            ndigs: ['dig1'],
            sn: 1,
            isith: 1,
            nsith: 1,
            adds: ['witA', 'witA'],
        };

        let error: unknown;
        try {
            rotate(args);
        } catch (err) {
            error = err;
        }

        assert.instanceOf(error, Error);
        assert.match(
            (error as Error).message,
            /Invalid adds = witA,witA, has duplicates/,
        );
    });

    it('rejects duplicate witness cuts', () => {
        const args = {
            keys: ['key2'],
            pre: 'pre2',
            ndigs: ['dig2'],
            sn: 1,
            isith: 1,
            nsith: 1,
            cuts: ['witB', 'witB'],
        };

        let error: unknown;
        try {
            rotate(args);
        } catch (err) {
            error = err;
        }

        assert.instanceOf(error, Error);
        assert.match(
            (error as Error).message,
            /Invalid cuts = witB,witB, has duplicates/,
        );
    });

    it('accepts unique cuts and adds without collisions', () => {
        const serder = rotate({
            keys: ['key3'],
            pre: 'pre3',
            ndigs: ['dig3'],
            sn: 1,
            isith: 1,
            nsith: 1,
            wits: ['witC'],
            cuts: ['witC'],
            adds: ['witD'],
        });

        assert.deepEqual(serder.sad.br, ['witC']);
        assert.deepEqual(serder.sad.ba, ['witD']);
    });
});
