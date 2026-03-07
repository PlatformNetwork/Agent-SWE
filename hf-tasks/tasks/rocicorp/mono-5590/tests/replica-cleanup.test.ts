import {afterEach, describe, expect, test, vi} from 'vitest';
import {LogContext} from '@rocicorp/logger';
import {DbFile} from '../../../test/lite.ts';
import {initializePostgresChangeSource} from './change-source.ts';

type ReplicaRow = {slot: string};

const replicaRows: ReplicaRow[] = [];

const resetReplicas = () => {
  replicaRows.splice(0, replicaRows.length,
    {slot: 'app_1_100'},
    {slot: 'app_1_200'},
    {slot: 'app_1_300'},
  );
};

resetReplicas();

const fakeSql = (strings: TemplateStringsArray | string, ...values: unknown[]) => {
  if (typeof strings === 'string') {
    return {text: strings};
  }

  let text = strings[0] ?? '';
  values.forEach((value, index) => {
    if (value && typeof value === 'object' && 'text' in (value as object)) {
      text += (value as {text: string}).text;
    } else if (Array.isArray(value)) {
      text += value.join(',');
    } else {
      text += String(value);
    }
    text += strings[index + 1] ?? '';
  });

  if (/FROM\s+pg_publication/i.test(text) && /SELECT/i.test(text)) {
    return {
      values: async () => ['zero_foo', 'zero_zero'],
      then: (resolve: (rows: {pubname: string}[]) => void) =>
        resolve([
          {pubname: 'zero_foo'},
          {pubname: 'zero_zero'},
        ]),
    };
  }

  if (/FROM\s+pg_replication_slots/i.test(text) && /SELECT/i.test(text)) {
    return Promise.resolve([
      {slot: 'app_1_200', pid: null},
      {slot: 'app_1_100', pid: null},
    ]);
  }

  if (/DELETE\s+FROM/i.test(text) && /replicas/i.test(text)) {
    const match = text.match(/slot\s*([!<>=]+)\s*([^\s;]+)/i);
    if (match) {
      const comparator = match[1];
      const keepSlot = match[2];
      if (comparator === '<') {
        const remaining = replicaRows.filter(row => row.slot >= keepSlot);
        replicaRows.splice(0, replicaRows.length, ...remaining);
      } else if (comparator === '!=') {
        const remaining = replicaRows.filter(row => row.slot === keepSlot);
        replicaRows.splice(0, replicaRows.length, ...remaining);
      }
    }
    return Promise.resolve([]);
  }

  return Promise.resolve([]);
};
(fakeSql as typeof fakeSql & {end?: () => Promise<void>}).end = async () => {};

vi.mock('../../../types/pg.ts', async () => {
  const actual = await vi.importActual<typeof import('../../../types/pg.ts')>(
    '../../../types/pg.ts',
  );
  return {
    ...actual,
    pgClient: () => fakeSql,
  };
});

vi.mock('./schema/init.ts', () => ({
  updateShardSchema: vi.fn(async () => {}),
}));

vi.mock('./schema/shard.ts', async () => {
  const actual = await vi.importActual<typeof import('./schema/shard.ts')>(
    './schema/shard.ts',
  );
  return {
    ...actual,
    getInternalShardConfig: vi.fn(async () => ({
      publications: ['zero_foo', 'zero_zero'],
      ddlDetection: false,
    })),
    getReplicaAtVersion: vi.fn(async () => ({
      slot: 'app_1_200',
      version: 'replica-version',
      initialSchema: {tables: {}, indexes: {}},
      publications: ['zero_foo', 'zero_zero'],
    })),
  };
});

vi.mock('./logical-replication/stream.ts', () => ({
  subscribe: vi.fn(async () => {
    throw new Error('subscribe should not run');
  }),
}));

vi.mock('../../replicator/schema/replication-state.ts', () => ({
  getSubscriptionState: vi.fn(() => ({
    replicaVersion: 'replica-version',
    publications: ['zero_foo', 'zero_zero'],
  })),
}));

vi.mock('./sync-schema.ts', () => ({
  initSyncSchema: vi.fn(async () => {}),
}));

describe('replica cleanup behavior', () => {
  afterEach(() => {
    resetReplicas();
  });

  test('preserves newer replicas when cleaning up older slots', async () => {
    const lc = new LogContext('error');
    const replicaFile = new DbFile('replica_cleanup_test');

    const {changeSource} = await initializePostgresChangeSource(
      lc,
      'postgres://user:pass@localhost/db',
      {
        appID: 'app',
        shardNum: 1,
        publications: ['zero_foo', 'zero_zero'],
      },
      replicaFile.path,
      {tableCopyWorkers: 1},
    );

    let err: unknown;
    try {
      await changeSource.startStream('00');
    } catch (e) {
      err = e;
    }

    expect(err).toBeInstanceOf(Error);
    expect(replicaRows).toEqual([
      {slot: 'app_1_200'},
      {slot: 'app_1_300'},
    ]);
    expect(replicaRows.some(row => row.slot === 'app_1_100')).toBe(false);
  });
});
