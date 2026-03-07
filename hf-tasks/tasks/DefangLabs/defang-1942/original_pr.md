# DefangLabs/defang-1942 (original PR)

DefangLabs/defang (#1942): chore: add deployment_id to ProjectUpdate proto

## Description

* add deployment ID (etag)
* remove unused `Event` message
* remove unused `Publish` rpc

## Linked Issues

<!-- See https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue -->

## Checklist

- [x] I have performed a self-review of my code
- [ ] I have added appropriate tests
- [ ] I have updated the Defang CLI docs and/or README to reflect my changes, if necessary



<!-- This is an auto-generated comment: release notes by coderabbit.ai -->
## Summary by CodeRabbit

* **Removed Features**
  * Message publishing endpoints and related client publish/send commands have been removed across the CLI and service surface.

* **API Changes**
  * Project update payloads now include an Etag (deployment ID) field to improve tracking of deployments.
<!-- end of auto-generated comment: release notes by coderabbit.ai -->
