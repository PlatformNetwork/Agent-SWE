// pyly-not-src-test

import { describe, expect, test, vi } from "vitest";

describe(`IconImage size prop`, () => {
  test(`size 20 maps to a 20px class`, async () => {
    vi.resetModules();

    vi.doMock(`#client/ui/IconImage.utils.ts`, () => ({
      iconRegistry: { flag: `mock-flag` },
      classNameLintInvariant: () => null,
    }));

    const { IconImage } = await import("#client/ui/IconImage.tsx");

    const element = IconImage({ icon: `flag`, size: 20 });

    expect(element).toBeTruthy();
    expect(element.props.className).toContain(`size-[20px]`);
  });
});
