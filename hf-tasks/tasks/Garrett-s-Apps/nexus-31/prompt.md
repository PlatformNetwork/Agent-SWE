# Garrett-s-Apps/nexus-31

Prevent CLI sessions from timing out or silently hanging during long-running autonomous work, especially in Docker. Ensure the CLI can write necessary state in read-only containers, uses the intended default model consistently with native execution, allows multi-hour idle periods without terminating, and reports stall timeout durations accurately. The system should tolerate long-running tasks with periodic output without premature termination.
