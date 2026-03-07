# IBM/JTOpen-310

Enable opting into virtual threads for the library’s background work instead of platform threads. Provide a configurable option (analogous to the existing thread-usage setting) on relevant client objects so users can select virtual threads when running on compatible Java versions, while remaining compatible with older Java runtimes. Specify that behavior should fall back appropriately when virtual threads are unavailable.
