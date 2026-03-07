# guardian/dotcom-rendering-15398 (original PR)

guardian/dotcom-rendering (#15398): Support football match header client-side only rendering

## What does this change?

Updates `FootballMatchHeader` to allow it to be fully client-side rendered on pages where match data is unavailable. The `match`, `tabs` and `leagueName` props have been combined into a single `initialData` prop. If this is undefined a placeholder is shown, and match data fetched and rendered on the client.

## Why?

On live and summary pages match data is not available as part of the page's data model due to our [_Core Development Principles (lines in the sand)_](https://github.com/guardian/frontend/blob/89ab47428b28a65b53af8600a1da2c427e5bfdb2/README.md?plain=1#L11):

> Each request may only perform one I/O operation on the backend. (you cannot make two calls to the content API or any other 3rd party)

Because of this we're unable to render the match header on the server due to not having the required data. By making the match data props optional we can use the header's existing ability to poll the match header endpoint to fetch data and render on the client.
