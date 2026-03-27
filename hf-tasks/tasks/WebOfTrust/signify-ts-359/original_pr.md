# WebOfTrust/signify-ts-359 (original PR)

WebOfTrust/signify-ts (#359): fix: use proper adds and cuts for rotate

Just noticed this the other day and realized it was a bug. The old code would not check for duplicates properly.

Edit: I changed the PR to reflect Fergal's suggestion. Now the _adds and _cuts are removed.
