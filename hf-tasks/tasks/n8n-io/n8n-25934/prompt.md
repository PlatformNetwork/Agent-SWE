# n8n-io/n8n-25934

Update the workflow SDK to eliminate the unused proxy-based expression serialization feature. Remove the deprecated expression-serialization utility and any user-visible APIs or types that exist solely to support it, leaving the string-based expression helper as the only supported expression mechanism. Ensure the public surface no longer exposes those unused expression types or utilities.
