# audeering/audb-544 (original PR)

audeering/audb (#544): Speedup looking for missing files in load_media()

Closes #543 

This speedups `audb.load_media(media, name)`. If `media` is of length `n` and the dataset `name` contains `m` media files, the speed increase is changing from O(n×m) to O(n+m).
