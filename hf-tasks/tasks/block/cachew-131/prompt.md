# block/cachew-131

Add support for Git maintenance for mirror repositories. When maintenance is enabled via configuration, ensure each mirror repository is registered for incremental maintenance after cloning and when existing mirrors are discovered on startup. Also initialize system-level Git maintenance scheduling on startup when maintenance is enabled. Default behavior should keep maintenance disabled.
