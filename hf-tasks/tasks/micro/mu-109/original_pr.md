# micro/mu-109 (original PR)

micro/mu (#109): Fix places search: timeout, larger radius, sort order, improved map links

Places search was erroring due to an HTTP client timeout (15s) shorter than the Overpass API's server-side query timeout (`[timeout:25]`), causing the client to abort before a response arrived. Radius was also capped at 5km, too small for urban use cases like finding a cinema that requires transit.

## Changes

- **Timeout**: `httpClient` timeout raised from `15s` → `35s` to outlast Overpass's 25s query execution window
- **Radius**: Max increased from `5km` → `50km` in both `handleSearch` and `handleNearby`; UI dropdown gains 10km / 25km / 50km options
- **Sort order**: Added sort dropdown (`distance` / `name`) to search form; applied via extracted `sortPlaces()` helper in both handlers; result count line shows active sort
- **Map links**:
  - Label changed from `"View on Google Maps"` → `"View on Map"`
  - Business name now included in both view and directions URLs so Google Maps resolves the correct place:
    ```
    https://maps.google.com/?q=Business+Name+lat,lon
    https://www.google.com/maps/dir/?api=1&destination=Business+Name&destination_latlng=lat,lon
    ```

<!-- START COPILOT CODING AGENT TIPS -->
---

💬 We'd love your input! Share your thoughts on Copilot coding agent in our [2 minute survey](https://gh.io/copilot-coding-agent-survey).

