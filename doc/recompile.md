# Recompile

A great way how to make sure your schema objects are valid.
It shows you how many objects you have, how many were fixed and how many remains invalid.

You can limit the scope by passing the object type and/or object name:

```
adt recompile -type {OBJECT_TYPE%}
adt recompile -type PACKAGE%
```
```
adt recompile -name {OBJECT_NAME%}
adt recompile -name XX%
```

You can specify target environment and/or target scheme:

```
adt recompile -target {ENVIRONMENT}
adt recompile -target UAT
```
```
adt recompile -schema {SCHEMA_NAME}
adt recompile -schema XX
```

You can force recompilation even on valid objects, that way you can set some flags like:

```
adt recompile -force -scope IDENTIFIERS
adt recompile -force -scope STATEMENTS
adt recompile -force -scope IDENTIFIERS STATEMENTS
```
```
adt recompile -force -warnings SEVERE
adt recompile -force -warnings SEVERE PERF
adt recompile -force -warnings SEVERE PERF INFO
```

You can also change from interpreted mode to native or vice versa:

```
adt recompile -force -native
adt recompile -force -interpreted
```

You can set the optimization level:

```
adt recompile -force -level 1
adt recompile -force -level 2
adt recompile -force -level 3
```

And of course you can combine all of these together.
