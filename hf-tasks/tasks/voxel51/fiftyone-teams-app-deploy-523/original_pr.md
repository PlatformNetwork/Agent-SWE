# voxel51/fiftyone-teams-app-deploy-523 (original PR)

voxel51/fiftyone-teams-app-deploy (#523): chore(versions): Bump for 2.16.2

# Rationale

Bumping versions for 2.16.2 release.

<!-- Please also assign a priority label to the PR. -->
Review Priority

* [x] high
* [ ] medium
* [ ] low

## Changes

```
for file in $(ack -l '2\.16\.1'); do perl -pi -e 's/2\.16\.1/2.16.2/g' $file; done
```

Also ignores fixture files to avoid breaking tests.

Checklist

* [x] This PR maintains parity between Docker Compose and Helm

## Testing

<!-- Describe the way the changes were tested. -->

<!-- Optional Sections:

## Screenshots
## To Do
## Notes
## Related

-->

<!-- Template for collapsed sections
<details>
<summary></summary>
</details>
-->

