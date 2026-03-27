# IBM/JTOpen-310 (original PR)

IBM/JTOpen (#310): Virtual threads

Hi, with this PR it will be possible to use virtual threads instead of platform threads.
The threads are instantiated using reflection so the change is compatible with versions of Java < 19.

This setting can be specified similarly to useThread with the virtualThreads property on a Datasource, AS400 object etc.
