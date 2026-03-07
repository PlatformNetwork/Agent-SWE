# DefangLabs/defang-1942

Add a deployment identifier (etag) to project update payloads so consumers can track deployments. Remove support for message publishing features, including any associated endpoints and commands, since they are no longer used. Ensure any references to the removed message publishing API are eliminated. No tests or documentation updates are required unless necessary to match the new API behavior.
