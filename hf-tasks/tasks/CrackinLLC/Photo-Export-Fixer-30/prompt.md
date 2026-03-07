# CrackinLLC/Photo-Export-Fixer-30

Update the GUI with the following user-facing fixes: limit mouse wheel scrolling so it only affects the scrollable area when the pointer is over it; ensure the application window appears immediately by performing any ExifTool availability check asynchronously; cap any displayed progress percentage at a maximum of 100%; and on Linux, store and load the settings file from the directory specified by XDG_CONFIG_HOME when it is set. No other GUI changes are in scope.
