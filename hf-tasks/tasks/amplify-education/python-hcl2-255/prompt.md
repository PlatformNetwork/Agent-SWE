# amplify-education/python-hcl2-255

Update object key expression handling so that keys can include characters that are not valid identifiers when written as plain strings (e.g., ":"). Keys should accept expressions without requiring extra parentheses, and interpolated string keys should not be wrapped in additional double quotes.
