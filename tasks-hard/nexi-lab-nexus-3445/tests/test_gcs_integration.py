@@ -40,7 +40,7 @@ class InMemoryBlobStore:
 
     Used to replace the real GCS client/bucket/blob objects in tests.
     Stores blobs as {key: bytes} and provides the minimal interface
-    needed by GCSBlobTransport.
+    needed by GCSTransport.
     """
 
     def __init__(self) -> None:
