# relational-calculus

This is an ugly hack to evaluate if relational calculus (specifically, Domain
Relational Calculus) can be better suited than SQL for most simple queries with
a few joins.

Two command-line arguments are expected. The first gives the query variables in
output order. The second gives a query in DRC using a superset of the query
variables and possibly additional string constants.

Example query on the example.txt database:

```
$ ./relq S,SD,L,LD 'student(S,SD) && immatriculated(S,"2016") && lecture(L,LD) && registered(S,L)' < example.txt
jane    "Jane Dane"     algebra1        "Algebra 1"
jane    "Jane Dane"     proglang1       "Introduction to Programming Languages"
john    "John Doe"      algebra1        "Algebra 1"
```

Try also the `--debug` switch to see the SQL produced internally.

If some column is not interesting an asterisk can be used
instead of a variable name.

```
$ ./relq S,SD 'student(S,SD) && registered(S,*)' < example.txt 
jack	"Jack of all Trades"
jane	"Jane Dane"
john	"John Doe"
```

This queries all students that are registered for any lecture at all.

Negation is done with an exclamation mark:

```
$ ./relq S 'student(S,*) && !registered(S,"proglang1")' < example.txt
john
```

External variable bindings can be given with a `-vVARIABLE=VALUE` argument:

```
$ L=proglang1
$ ./relq -vL="$L" S 'student(S,*) && !registered(S,L)' < example.txt
john
```

This is to free the caller from the burden of escaping the value correctly.

Important features are still missing, like integer values, schema syntax and
comparison predicates.
