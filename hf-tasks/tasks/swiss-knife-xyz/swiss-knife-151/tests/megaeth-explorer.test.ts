import assert from "node:assert/strict";

import { addressExplorers } from "../data/addressExplorers";
import {
  chainIdToChain,
  chainIdToImage,
  etherscanChains,
} from "../data/common";
import { generateUrl } from "../utils";
import { ExplorerType } from "../types";

const MEGAETH_CHAIN_ID = 4326;
const sampleAddress = "0x1234567890abcdef1234567890abcdef12345678";
const sampleTx =
  "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd";

const megaethChain = Object.values(etherscanChains).find(
  (chain) => chain.id === MEGAETH_CHAIN_ID
);
assert.ok(megaethChain, "MegaETH should be listed in etherscanChains");
assert.equal(megaethChain?.name, "MegaETH");
assert.equal(
  megaethChain?.blockExplorers?.default?.url,
  "https://mega.etherscan.io"
);

const chainFromMap = chainIdToChain[MEGAETH_CHAIN_ID];
assert.ok(chainFromMap, "MegaETH should be mapped in chainIdToChain");
assert.equal(chainFromMap?.name, "MegaETH");
assert.equal(
  chainIdToImage[MEGAETH_CHAIN_ID],
  "/chainIcons/megaeth.svg",
  "MegaETH should have a chain icon mapping"
);

const megaethExplorer = addressExplorers["MegaETH Explorer"];
assert.ok(megaethExplorer, "MegaETH Explorer entry should exist");
assert.equal(
  megaethExplorer.urlLayout,
  "https://mega.etherscan.io/address/$SK_ADDRESS"
);
assert.equal(megaethExplorer.chainIdToLabel[MEGAETH_CHAIN_ID], "");

const generatedAddressUrl = generateUrl(
  megaethExplorer.urlLayout,
  megaethExplorer.chainIdToLabel[MEGAETH_CHAIN_ID],
  sampleAddress,
  ExplorerType.ADDRESS
);
assert.equal(
  generatedAddressUrl,
  `https://mega.etherscan.io/address/${sampleAddress}`
);

const generatedTxUrl = generateUrl(
  "https://mega.etherscan.io/tx/$SK_TX",
  "",
  sampleTx,
  ExplorerType.TX
);
assert.equal(
  generatedTxUrl,
  `https://mega.etherscan.io/tx/${sampleTx}`
);

console.log("MegaETH explorer integration tests passed.");
