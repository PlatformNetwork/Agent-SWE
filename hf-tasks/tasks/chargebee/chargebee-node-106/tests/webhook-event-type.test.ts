import { expect } from 'chai';
import Chargebee from '../src/chargebee.esm.js';
import * as ChargebeeCjs from '../src/chargebee.cjs.js';
import {
  WebhookHandler,
  WebhookEventType,
} from '../src/resources/webhook/handler.js';

const makeEventBody = (eventType: string, content: string = '{}') => {
  return JSON.stringify({
    id: 'evt_test_enum_1',
    occurred_at: Math.floor(Date.now() / 1000),
    event_type: eventType,
    content: JSON.parse(content),
  });
};

describe('WebhookEventType exports', () => {
  it('should be exported from the main ESM module', () => {
    expect((Chargebee as any).WebhookEventType).to.equal(WebhookEventType);
    expect(WebhookEventType.SubscriptionCancelled).to.equal(
      'subscription_cancelled',
    );
  });

  it('should be exported from the main CJS module', () => {
    expect((ChargebeeCjs as any).WebhookEventType).to.equal(WebhookEventType);
    expect(WebhookEventType.InvoiceGenerated).to.equal('invoice_generated');
  });
});

describe('WebhookHandler with WebhookEventType enum', () => {
  it('should route events using WebhookEventType enum values', async () => {
    const handler = new WebhookHandler();
    let subscriptionCancelledCalled = false;
    let invoiceGeneratedCalled = false;

    handler.on(WebhookEventType.SubscriptionCancelled, async () => {
      subscriptionCancelledCalled = true;
    });
    handler.on(WebhookEventType.InvoiceGenerated, async () => {
      invoiceGeneratedCalled = true;
    });

    await handler.handle({
      body: makeEventBody(WebhookEventType.SubscriptionCancelled),
    });
    await handler.handle({
      body: makeEventBody(WebhookEventType.InvoiceGenerated),
    });

    expect(subscriptionCancelledCalled).to.equal(true);
    expect(invoiceGeneratedCalled).to.equal(true);
  });

  it('should emit unhandled_event when no listener matches enum value', async () => {
    const handler = new WebhookHandler();
    let unhandledCalled = false;

    handler.on('unhandled_event', async ({ event }) => {
      unhandledCalled = true;
      expect(event.event_type).to.equal(
        WebhookEventType.SubscriptionPaused,
      );
    });

    await handler.handle({
      body: makeEventBody(WebhookEventType.SubscriptionPaused),
    });

    expect(unhandledCalled).to.equal(true);
  });
});
