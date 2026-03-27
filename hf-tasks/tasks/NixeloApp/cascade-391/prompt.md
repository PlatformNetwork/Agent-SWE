# NixeloApp/cascade-391

Refactor the fast-path user stats counting logic to reduce duplication and keep the existing behavior. Ensure the counting for issues by reporter and assignee still works correctly using a shared approach, with no changes to user-visible results.
