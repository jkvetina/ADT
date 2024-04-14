# Search Repo

Did you ever wanted to search on your commits?
Did you ever wanted to see a history for a specific file?
Or an object name because your file names keep changing?
Or to know when the file/object was deleted from repo?

To check all available arguments:

```
adt search_repo
```

The output contains info about commits, with summary, author, date and list of affected files, resp. database objects.
The searching is case insensitive 'contains' type and if you you provide more words, all of them must be found.

First you can search for specific commits by their number or hash.
You can also search the summary text:

```
adt search_repo -commit {COMMIT_NUMBER(S)}
adt search_repo -hash {COMMIT_HASH(ES)}
adt search_repo -summary {WORD(S)}
```

You can search for specific file, even if it doesnt exists anymore:

```
adt search_repo -file {CONTAIN(S)}
adt search_repo -file /packages XX
```

You can limit the scope for a specific branch or by recent days:

```
adt search_repo -branch {BRANCH_NAME}
adt search_repo -recent {DAYS}
```
