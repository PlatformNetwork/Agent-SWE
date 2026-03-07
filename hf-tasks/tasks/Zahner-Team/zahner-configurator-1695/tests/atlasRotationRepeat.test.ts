import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";

import { applyAtlasTiling } from "../../src/materials/core/atlasTiling";
import * as WorldTiling from "../../src/materials/system/worldTiling";

const createMaterial = () => {
  const mat = new THREE.MeshPhysicalMaterial();
  mat.map = new THREE.Texture();
  (mat.map as any).image = { width: 4, height: 4 };
  return mat;
};

const baseConfig = {
  atlasMode: "atlas",
  atlasInches: [200, 150] as [number, number],
  textureScale: 1,
  atlasJitter: 0,
  atlasBrick: false,
  scaleJitterPct: 0,
  uvShiftUPct: 0,
  uvShiftVPct: 0,
  tileJitterU: 0,
  tileJitterV: 0,
  cropShiftPctU: 0,
  cropShiftPctV: 0,
  edgeGuardIn: 0,
  angleJitterDeg: 0,
  flipProbability: 0,
  rotateWithPanel: false,
};

describe("atlas tiling rotation repeat mapping", () => {
  it("swaps face dimensions before scaling for odd rotations", () => {
    const spy = vi.spyOn(WorldTiling, "applyAtlasScalingForPanel");
    const mat = createMaterial();

    applyAtlasTiling([mat, null, null], {
      finishKey: "Standard",
      faceSizeInches: [30, 90],
      worldPosInches: [0, 0, 0],
      tileInches: 30,
      panelId: "panel-odd-1",
      rotate: 1,
    }, baseConfig, 17);

    expect(spy).toHaveBeenCalled();
    const args = spy.mock.calls[0]?.[0];
    expect(args?.faceInches).toEqual([30, 90]);
    expect(args?.faceInches).not.toEqual([90, 30]);
  });

  it("keeps normalized face ordering for even rotations", () => {
    const spy = vi.spyOn(WorldTiling, "applyAtlasScalingForPanel");
    const mat = createMaterial();

    applyAtlasTiling([mat, null, null], {
      finishKey: "Standard",
      faceSizeInches: [40, 100],
      worldPosInches: [0, 0, 0],
      tileInches: 40,
      panelId: "panel-even-0",
      rotate: 0,
    }, baseConfig, 23);

    expect(spy).toHaveBeenCalled();
    const args = spy.mock.calls[0]?.[0];
    expect(args?.faceInches).toEqual([100, 40]);
  });
});
