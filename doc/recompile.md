# Recompile

A great way how to make sure your schema objects are valid.
It shows you how many objects you have, how many were fixed and how many remains invalid.

You can limit the scope by passing the object type and name:

- `recompile.py -type __ -name __`
- `recompile.py -type PACKAGE% -name TSK%`

You can force recompilation even on valid objects, so you can set some flags like:

- `recompile.py -force -scope IDENTIFIERS STATEMENTS` [IDENTIFIERS | STATEMENTS | ALL]
- `recompile.py -force -warnings SEVERE` [SEVERE | PERF | INFO]

You can also change from interpreted mode to native or vice versa:

- `recompile.py -native`
- `recompile.py -interpreted`

You can set the optimization level:

- `recompile.py -level 2`  [1, 2, 3]

And of course you can combine all of these together.
