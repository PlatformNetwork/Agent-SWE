import { expect } from 'chai';
import {
  WebhookHandler,
  WebhookPayloadValidationError,
} from '../src/resources/webhook/handler.js';

const makeEventBody = (body: unknown) => {
  return JSON.stringify(body);
};

describe('WebhookHandler payload validation', () => {
  it('should reject payloads with non-string event_type', async () => {
    const handler = new WebhookHandler();
    let caughtError: unknown;

    try {
      await handler.handle({
        body: makeEventBody({
          id: 'evt_invalid_type',
          occurred_at: 171234,
          event_type: 12345,
          content: {},
        }),
      });
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).to.be.instanceOf(WebhookPayloadValidationError);
    expect((caughtError as Error).message).to.contain('event_type');
  });

  it('should reject payloads missing event id', async () => {
    const handler = new WebhookHandler();
    let caughtError: unknown;

    try {
      await handler.handle({
        body: makeEventBody({
          occurred_at: 171234,
          event_type: 'subscription_created',
          content: {},
        }),
      });
    } catch (err) {
      caughtError = err;
    }

    expect(caughtError).to.be.instanceOf(WebhookPayloadValidationError);
    expect((caughtError as Error).message).to.contain('event id');
  });
});
