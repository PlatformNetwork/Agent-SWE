const fs = require("fs");
const path = require("path");
const assert = require("assert");

const cssDir = path.join(process.cwd(), ".next", "static", "chunks");
assert.ok(fs.existsSync(cssDir), "Expected Next.js build chunks directory to exist");

const cssFiles = fs.readdirSync(cssDir).filter((file) => file.endsWith(".css"));
assert.ok(cssFiles.length > 0, "Expected at least one compiled CSS file");

const cssContent = cssFiles
  .map((file) => fs.readFileSync(path.join(cssDir, file), "utf8"))
  .join("\n");

function expectMatch(regex, message) {
  assert.ok(regex.test(cssContent), message);
}

expectMatch(
  /--color-foreground:\s*var\(--color-grey-10\)/,
  "Expected foreground color token to use grey-10"
);
expectMatch(
  /--color-text-primary:\s*var\(--color-grey-10\)/,
  "Expected primary text color token to use grey-10"
);

expectMatch(/--text-largest:\s*48px/, "Expected largest typography token");
expectMatch(/--text-header-28:\s*28px/, "Expected header-28 typography token");
expectMatch(/--text-header-24:\s*24px/, "Expected header-24 typography token");
expectMatch(/--text-body-14:\s*14px/, "Expected body-14 typography token");
expectMatch(
  /--text-caption-12-tight:\s*12px/,
  "Expected caption-12-tight typography token"
);

const textClassPatterns = [
  { name: "text-largest", size: "48px" },
  { name: "text-header-28", size: "28px" },
  { name: "text-header-24", size: "24px" },
  { name: "text-body-14", size: "14px" },
  { name: "text-caption-12-tight", size: "12px" },
];

for (const { name, size } of textClassPatterns) {
  const classRegex = new RegExp(
    `\\.${name}\\{[^}]*font-size:(?:var\\(--${name}\\)|${size})`
  );
  expectMatch(classRegex, `Expected ${name} utility class to set font-size`);
}

console.log("Typography token assertions passed.");
