# audeering/audb-544

Improve performance of loading media when checking for missing files. Ensure the process scales linearly with the number of requested media entries and the number of media files in the dataset, avoiding multiplicative slowdowns when inputs are large.
