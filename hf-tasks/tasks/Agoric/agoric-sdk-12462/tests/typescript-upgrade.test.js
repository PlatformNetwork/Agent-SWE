// @ts-check
import test from 'ava';
import path from 'node:path';
import fs from 'node:fs';
import ts from 'typescript';

const repoRoot = path.resolve(process.cwd(), '..', '..');

const parseConfig = configPath => {
  const text = fs.readFileSync(configPath, 'utf8');
  return ts.parseConfigFileTextToJson(configPath, text);
};

const assertParsedConfig = (t, configPath) => {
  const parsed = parseConfig(configPath);
  t.falsy(parsed.error, 'Expected tsconfig to parse without errors');
  t.truthy(parsed.config, 'Expected parsed config to be defined');
  return parsed.config ?? {};
};

test('access-token config removes allowSyntheticDefaultImports', t => {
  const configPath = path.resolve(
    repoRoot,
    'packages',
    'access-token',
    'tsconfig.json',
  );
  const config = assertParsedConfig(t, configPath);
  const { compilerOptions = {} } = config;
  t.is(compilerOptions.allowSyntheticDefaultImports, undefined);
  t.true('allowSyntheticDefaultImports' in compilerOptions === false);
});

test('client-utils build config removes downlevelIteration', t => {
  const configPath = path.resolve(
    repoRoot,
    'packages',
    'client-utils',
    'tsconfig.build.json',
  );
  const config = assertParsedConfig(t, configPath);
  const { compilerOptions = {} } = config;
  t.is(compilerOptions.downlevelIteration, undefined);
  t.true('downlevelIteration' in compilerOptions === false);
});

test('cosmic-proto build config removes downlevelIteration', t => {
  const configPath = path.resolve(
    repoRoot,
    'packages',
    'cosmic-proto',
    'tsconfig.build.json',
  );
  const config = assertParsedConfig(t, configPath);
  const { compilerOptions = {} } = config;
  t.is(compilerOptions.downlevelIteration, undefined);
  t.true('downlevelIteration' in compilerOptions === false);
});
