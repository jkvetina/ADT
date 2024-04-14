# Search APEX

Did you ever wanted to know which objects are used on which page(s)?
Or where is the specific object used in APEX? This script will show you exactly that.

Technically half of it is based on Embedded Code report, the other half queries your database to find Invoke API references.
So to make this work you need to export Embedded Code first and you have to be able to connect to your database.
See [export_apex](./export_apex.md) for more details.

To check all available arguments:

```
adt search_apex
```

First you can search for object used on specific page(s):
It will list database objects used or referenced on the page(s).
If you add patch_code, it will create a patch for these objects in patch_scripts/ folder.
Objects will be sorted by dependencies and grants will be included.

```
adt search_apex -app {APP_ID} -page {PAGE_ID(S)}
adt search_apex -app {APP_ID} -page {PAGE_ID(S)} -patch {PATCH_NAME}
```

You can limit the scope to show process just specific object types and/or object names:

```
adt search_apex -type {OBJECT_TYPE%}
adt search_apex -name {OBJECT_NAME%}
```

You can (and should) combine these options together. Keep in mind it is searching just for database objects.

If you have your APEX application in a different schema, you can use the schema prefix for faster and a tiny bit more precise searching:

```
adt search_apex -app {APP_ID} -schema {SCHEMA_NAME}
```
