# CrackinLLC/Photo-Export-Fixer-15

Enable cancellation during preview (dry run) so the cancel button works while a preview is running. When a user initiates preview and then clicks cancel, the preview should stop, show a confirmation dialog tailored for preview vs processing, and if confirmed, return to the setup view with a status indicating the preview was cancelled. Ensure preview cancellation checks are performed during the preview loop and that existing preview behavior remains backward compatible when no cancel event is provided. Do not change processing-mode cancellation behavior.
