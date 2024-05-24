# Auth0 export-import utility

# Overview

User this utility to migrate your Auth0 user database from one Auth0 tenant to another.

# How to use this tool?

## Prerequisites
1You know how to use the command line
2You have Python 3 installed
3. You downloaded the user export from Auth0 using the [import/export extension](https://auth0.com/docs/customize/extensions/user-import-export-extension).
4. You received an Auth0 password hash export after requesting one from them using their support ticketing system.

## Instructions
1. Save `auth0_import_export.py` locally
2. Run `python auth0_import_export <user_export_path> <password_hash_path> > file_to_import_into_auth0.json`
3. Use the [import/export extension](https://auth0.com/docs/customize/extensions/user-import-export-extension) and run an import using `file_to_import_into_auth0.json`

The user export path can point to the .gz file you got from Auth0. This program will also accept a json file (really ndjson), so if you already un-gzipped it, that's fine.

The password has file can point to the zip file that contains the hash export. It can also point to a json file, in case you unzipped the archive.

# Why use this tool?

_Auth0 is nice._

If you want to migrate your user database from one tenant (or account) to another tenant,
they provide a convenient import/export extension.

_Auth0 is silly._

If you export the user database from one tenants and try to import it into another tenant, it fails.
There are a few reasons:
- the export is in ndjson format, while the import expects regular json
- the export has emails in fields named "Email" while the import expects "email"

_Auth0 is confusing._

Even if you did the work above, you still will not be able to log into any of those accounts.
The export does not include password hashes. If you import that file, each person will need to do a password reset
before logging in.

__This tool takes care of all of the above.__

You can ask Auth0 for an additional export file that contains the password hashes.
You can use this program to combine the two exports into a file that can be imported
This program takes care of everything. It combines the two files and does the transformation. You can import
the output file of this program into Auth0.


# Need more help?

If you don't want to deal with this and would like someone to handle your Auth0 migration for you, go to koliber.com
or shoot an email to services@koliber.com.

Copyright 2024 Koliber Services - Krystian Cybulski - https://koliber.com - services@koliber.com
