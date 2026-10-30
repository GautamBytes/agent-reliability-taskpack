# Equivalent implementations

These controls must pass. They verify that holdout tests check the public contract without requiring the upstream reference's local variable names or one chosen SQL Server length.

The MySQL control renames the generated guard's local variable. The SQL Server control uses a bounded length of 200, which the public contract permits. Both include the complete attributed upstream production fix.

The Prisma control uses the documented named `fields:` argument and spaces inside its index attribute. Its generated output was accepted by an installed AST parser and the official Prisma formatter for MySQL, PostgreSQL and SQLite, offline. This checks schema syntax, not live database execution. See the portfolio-level `evidence/independent-review/prisma-formatting/` evidence.
