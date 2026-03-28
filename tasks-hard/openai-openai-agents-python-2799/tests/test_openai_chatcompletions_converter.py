@@ -140,6 +140,49 @@ def test_items_to_messages_with_easy_input_message():
     assert out["content"] == "How are you?"
 
 
+def test_items_to_messages_accepts_raw_chat_completions_user_content_parts():
+    """
+    Raw Chat Completions content parts should be accepted as aliases for the SDK's
+    canonical input content shapes.
+    """
+    items: list[TResponseInputItem] = [
+        # Cast the fixture because mypy cannot infer this raw chat-style dict as a specific
+        # member of the TResponseInputItem TypedDict union on its own.
+        cast(
+            TResponseInputItem,
+            {
+                "role": "user",
+                "content": [
+                    {"type": "text", "text": "What is in this image?"},
+                    {
+                        "type": "image_url",
+                        "image_url": {
+                            "url": "https://example.com/image.png",
+                            "detail": "high",
+                        },
+                    },
+                ],
+            },
+        )
+    ]
+
+    messages = Converter.items_to_messages(items)
+
+    assert len(messages) == 1
+    message = messages[0]
+    assert message["role"] == "user"
+    assert message["content"] == [
+        {"type": "text", "text": "What is in this image?"},
+        {
+            "type": "image_url",
+            "image_url": {
+                "url": "https://example.com/image.png",
+                "detail": "high",
+            },
+        },
+    ]
+
+
 def test_items_to_messages_with_output_message_and_function_call():
     """
     Given a sequence of one ResponseOutputMessageParam followed by a
