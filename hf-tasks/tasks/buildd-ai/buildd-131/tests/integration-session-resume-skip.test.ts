import { describe, test, expect } from 'bun:test';

const INTEGRATION_TEST_PATH = 'apps/local-ui/__tests__/integration-session-resume.test.ts';

async function runIntegrationTest() {
  const proc = Bun.spawn({
    cmd: ['bun', 'test', `./${INTEGRATION_TEST_PATH}`],
    env: {
      ...process.env,
      // Ensure the integration test runs its skip branch
      BUILDD_TEST_SERVER: '',
    },
    stdout: 'pipe',
    stderr: 'pipe',
  });

  const exitCode = await proc.exited;
  const stdout = await new Response(proc.stdout).text();
  const stderr = await new Response(proc.stderr).text();

  return { exitCode, output: `${stdout}${stderr}` };
}

describe('integration-session-resume test runner', () => {
  test('skips when BUILDD_TEST_SERVER is unset', async () => {
    const { exitCode, output } = await runIntegrationTest();

    expect(exitCode).toBe(0);
    expect(output).toContain('Skipping: BUILDD_TEST_SERVER not set.');
  }, 30000);
});
