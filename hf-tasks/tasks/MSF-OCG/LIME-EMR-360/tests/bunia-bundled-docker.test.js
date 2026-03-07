const assert = require('assert');
const { spawnSync } = require('child_process');

function runMavenEvaluate(expression, profiles = []) {
  const args = ['-q'];
  if (profiles.length) {
    args.push(`-P${profiles.join(',')}`);
  }
  args.push(
    '-f',
    'sites/bunia/pom.xml',
    'help:evaluate',
    `-Dexpression=${expression}`,
    '-DforceStdout'
  );
  const result = spawnSync('mvn', args, { encoding: 'utf-8' });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Maven exited with ${result.status}: ${result.stderr}`);
  }
  const lines = result.stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  return lines[lines.length - 1] || '';
}

// Default properties should resolve for Bunia after bundled-docker support
const defaultEnvironment = runMavenEvaluate('msf.environment');
assert.strictEqual(
  defaultEnvironment,
  'dev',
  `Expected default msf.environment to be dev, got ${defaultEnvironment}`
);

const defaultTag = runMavenEvaluate('bundled.docker.tag');
assert.strictEqual(
  defaultTag,
  'dev',
  `Expected default bundled.docker.tag to be dev, got ${defaultTag}`
);

// Production profile should override environment and tag
const productionEnvironment = runMavenEvaluate('msf.environment', ['production']);
assert.strictEqual(
  productionEnvironment,
  'latest',
  `Expected production msf.environment to be latest, got ${productionEnvironment}`
);

const productionTag = runMavenEvaluate('bundled.docker.tag', ['production']);
assert.strictEqual(
  productionTag,
  'latest',
  `Expected production bundled.docker.tag to be latest, got ${productionTag}`
);

// Bundled docker profile should expose docker bundle properties
const bundledVersion = runMavenEvaluate('ozoneBundledDocker', ['bundled-docker']);
assert.strictEqual(
  bundledVersion,
  '1.0.0-alpha.13',
  `Expected ozoneBundledDocker to be 1.0.0-alpha.13, got ${bundledVersion}`
);

const groovyTemplateVersion = runMavenEvaluate('groovyTemplatesVersion', ['bundled-docker']);
assert.strictEqual(
  groovyTemplateVersion,
  '3.0.22',
  `Expected groovyTemplatesVersion to be 3.0.22, got ${groovyTemplateVersion}`
);

console.log('Bundled docker Maven profile properties resolved as expected.');
