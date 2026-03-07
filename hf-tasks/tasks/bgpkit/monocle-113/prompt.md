# bgpkit/monocle-113

Update the application’s configuration, data, and cache directory behavior to follow the XDG Base Directory specification. Use the appropriate XDG environment variables with sensible fallbacks to the standard user home subdirectories when the variables are not set. Ensure any cache storage uses the XDG cache location. Preserve existing functionality while changing the expected on-disk locations accordingly.
