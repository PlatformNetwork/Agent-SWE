# WebOfTrust/signify-ts-359

Fix rotation processing so duplicate detection works correctly. Ensure key rotation handles additions and removals properly without allowing duplicates, and remove any unnecessary legacy fields related to adds/cuts from the rotation request or processing.
