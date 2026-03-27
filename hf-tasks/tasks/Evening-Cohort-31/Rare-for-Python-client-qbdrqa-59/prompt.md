# Evening-Cohort-31/Rare-for-Python-client-qbdrqa-59

Implement post tag management in the post UI so users can add and remove tags directly, with search, tag limits, and immediate persistence. Update the post detail view to use the enhanced post component and only show edit/tag controls to the post owner.

Add a dedicated route for editing posts at /post/edit/:id and update navigation to use it. Adjust the post form usage to rely on an explicit edit mode flag rather than query parameters.

Fix admin detection and improve the admin guard to surface failed checks during development. Improve the post approval flow to handle loading and error states and only update the UI after approval is confirmed by the backend.
