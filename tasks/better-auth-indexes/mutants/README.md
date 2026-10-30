# Partial-fix controls

Each patch applies to the clean upstream baseline, not on top of the reference patch. They are deliberately incomplete production fixes. The verifier restores all tests independently.

| Patch | Missing behavior |
| --- | --- |
| `schema_only.patch` | Adds plugin lookup metadata but leaves generator and code-result boundaries incomplete. |
| `mysql_without_existence_guard.patch` | Creates valid indexes but omits table/index existence protection for repeated MySQL generation. |
| `utf16_index_names.patch` | Measures JavaScript string length instead of UTF-8 bytes, so non-ASCII identifiers exceed the portable limit. |
| `unchecked_custom_codes.patch` | Implements indexing and configured bounds while trusting invalid custom generator results. |

These controls were authored for the evaluation task. They are not described as changes rejected by upstream maintainers.
