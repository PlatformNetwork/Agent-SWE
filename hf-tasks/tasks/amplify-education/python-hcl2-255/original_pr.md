# amplify-education/python-hcl2-255 (original PR)

amplify-education/python-hcl2 (#255): fix: Support writing keys with invalid chars

This actually fixes a few of things related to expressions for object keys:
1. It allows they keys contain characters that aren't valid as identifiers, if the key is a plain string, for example: ":"
2. It removes the need for superflouous parenthesis around expresions in the keys
3. It no longer puts double quotes around an interpolated string in the key.

The second two were actually kind of side-affects of my fix for 1.

If we want to preserve the previous behavior for 2 and 3, I think it wouldn't be too hard to do though.
