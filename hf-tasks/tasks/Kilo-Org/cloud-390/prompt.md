# Kilo-Org/cloud-390

Ensure the git protocol handling in the app builder provides consistent shared behavior and correct pkt-line formatting. Advertise the default branch via the symref=HEAD:<branch> capability in both upload-pack and receive-pack info/refs responses so git clients can detect the default branch on clone and push. Fix pkt-line length calculation to use UTF-8 byte length rather than JavaScript string length so multi-byte characters are handled correctly.
