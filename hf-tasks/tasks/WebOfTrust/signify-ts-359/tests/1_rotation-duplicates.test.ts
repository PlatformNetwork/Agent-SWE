import { assert, beforeEach, describe, it, vitest } from 'vitest';
import libsodium from 'libsodium-wrappers-sumo';
import { randomUUID } from 'node:crypto';
import {
    Controller,
    Identifier,
    IdentifierDeps,
    IdentifierManagerFactory,
    Tier,
} from '../../src/index.ts';
import { createMockIdentifierState } from './test-utils.ts';

const bran = 'abcdef0123456789ghijk';

class MockClient implements IdentifierDeps {
    manager: IdentifierManagerFactory;
    controller: Controller;

    fetch = vitest.fn();

    constructor(branValue: string) {
        this.controller = new Controller(branValue, Tier.low);
        this.manager = new IdentifierManagerFactory(this.controller.salter);
    }

    identifiers() {
        return new Identifier(this);
    }

    getLastMockRequest() {
        const [pathname, method, body] = this.fetch.mock.lastCall ?? [];
        return { path: pathname, method, body };
    }
}

describe('Identifier rotation witness duplication handling', () => {
    let client: MockClient;

    beforeEach(async () => {
        await libsodium.ready;
        client = new MockClient(bran);
    });

    it('rejects rotation requests with duplicate witness additions', async () => {
        const aid = await createMockIdentifierState(randomUUID(), bran);

        client.fetch.mockResolvedValueOnce(Response.json(aid, { status: 200 }));
        client.fetch.mockResolvedValueOnce(Response.json({}, { status: 202 }));

        let error: unknown;
        try {
            await client.identifiers().rotate(aid.name, {
                adds: ['witX', 'witX'],
            });
        } catch (err) {
            error = err;
        }

        assert.instanceOf(error, Error);
        assert.match(
            (error as Error).message,
            /Invalid adds = witX,witX, has duplicates/,
        );
    });

    it('allows distinct witness cut/add updates without duplicates', async () => {
        const aid = await createMockIdentifierState(randomUUID(), bran, {
            wits: ['wit1', 'wit2'],
            toad: 1,
        });

        client.fetch.mockResolvedValueOnce(Response.json(aid, { status: 200 }));
        client.fetch.mockResolvedValueOnce(Response.json({}, { status: 202 }));

        await client.identifiers().rotate(aid.name, {
            cuts: ['wit1'],
            adds: ['wit3'],
        });

        const request = client.getLastMockRequest();
        assert.equal(request.path, `/identifiers/${aid.name}/events`);
        assert.deepEqual(request.body.rot.br, ['wit1']);
        assert.deepEqual(request.body.rot.ba, ['wit3']);
    });
});
