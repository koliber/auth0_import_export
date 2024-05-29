# Copyright 2024 Koliber Services - Krystian Cybulski
#
# Auth0 is nice.
# If you want to migrate your user database from one tenant (or account) to another tenant,
# they provide a convenient import/export extension.
#
# Auth0 is silly.
# If you export the user database from one tenants and try to import it into another tenant, it fails.
# There are a few reasons:
# - the export is in ndjson format, while the import expects regular json
# - the export has emails in fields named "Email" while the import expects "email"
#
# Auth0 is confusing.
# Even if you did the work above, you still will not be able to log into any of those accounts.
# The export does not include password hashes. If you import that file, each person will need to do a password reset
# before logging in.
#
# There's a solution.
# You can ask Auth0 for an additional export file that contains the password hashes.
# You can use this program to combine the two exports into a file that can be imported
# This program takes care of everything. It combines the two files and does the transformation. You can import
# the output file of this program into Auth0
#
# If you don't want to deal with this and would like someone to handle your Auth0 migration for you, go to koliber.com
# or shoot an email to services@koliber.com.

import gzip
import json
import sys
import zipfile


def get_user_lines(users_file: str) -> list[str]:
    # assume the file is gzip, as that is how auth0 exports it.
    try:
        with gzip.open(users_file, 'rt') as file:
            return file.readlines()
    except gzip.BadGzipFile:
        # fall back and try reading the file as plain text, as perhaps the user already un-gzipped it
        with open(users_file, 'r') as file:
            return file.readlines()


def verify_valid_ndjson_lines(ndjson_lines: list[str]) -> bool:
    output_json = "[" + ",".join(ndjson_lines) + "]"
    try:
        json.loads(output_json)
        return True
    except json.JSONDecodeError:
        return False


def get_hash_lines(hashes_file_path: str) -> list[str]:
    # assume the hashes file is zipped, as that is how auth0 exports it.
    try:
        with zipfile.ZipFile(hashes_file_path, 'r') as zip_file:
            # Get the name of the single file in the zip archive
            file_names = zip_file.namelist()
            if len(file_names) != 1:
                print("The zip file with the hash export should contain exactly one file: " + hashes_file_path, file=sys.stderr)
                exit(-1)

            inner_file_name = file_names[0]

            with zip_file.open(inner_file_name, 'r') as file:
                lines = file.readlines()
                # Decode bytes to strings
                lines = [line.decode('utf-8') for line in lines]
        return lines
    except zipfile.BadZipFile:
        # fall back and try reading the file as plain text, as perhaps the user already unzipped it
        with open(hashes_file_path, 'r') as file:
            return file.readlines()


def get_user_info_by_email(users_file_path: str) -> dict[str, dict[str, str]]:
    user_lines = get_user_lines(users_file_path)
    if not verify_valid_ndjson_lines(user_lines):
        print('The users export file contains invalid json (ndjson) content: ' + users_file_path, file=sys.stderr)
        exit(-1)

    user_info_by_email = {}
    for user_line in user_lines:
        user_json = json.loads(user_line)
        email = user_json['Email']
        user_info_by_email[email] = user_json

    return user_info_by_email


def get_password_hashes_by_email(hashes_file_path: str) -> dict[str, dict[str, str]]:
    hash_lines = get_hash_lines(hashes_file_path)
    if not verify_valid_ndjson_lines(hash_lines):
        print('The password hash export file contains invalid json (ndjson) content: ' + hashes_file_path, file=sys.stderr)
        exit(-1)

    hash_info_by_email = {}
    for user_line in hash_lines:
        hash_json = json.loads(user_line)
        email = hash_json['email']  # it really is lower-cased in this file
        hash_info_by_email[email] = hash_json

    return hash_info_by_email


def get_auth0_db_name(password_hashes_by_email: dict[str, dict[str, str]]) -> str:
    a_hash_entry = next(iter(password_hashes_by_email.items()))[1]
    # The "connection" is the database name in Auth0 that houses locally-stored users
    return a_hash_entry['connection']


def create_auth0_import(users_file_path: str, hashes_file_path: str):
    user_info_by_email = get_user_info_by_email(users_file_path)
    if not user_info_by_email:
        print('No users found in the file: ' + users_file_path, file=sys.stderr)
        exit(0)
    password_hashes_by_email = get_password_hashes_by_email(hashes_file_path)
    if not user_info_by_email:
        print('No password hashes found in the file: ' + hashes_file_path, file=sys.stderr)
        exit(0)

    # Each user that has a matching "Connection" value should have a hash in the hashes file.
    # Keep track of this for information purposes.
    database_name = get_auth0_db_name(password_hashes_by_email)

    users_with_missing_passwords: list[str] = []

    output: list[dict[str, str]] = []
    for email, user_info in user_info_by_email.items():
        # The output file needs a lower-cased "email"
        user_info['email'] = user_info.pop('Email')
        user_info['email_verified'] = user_info.pop('Email Verified')
        given_name = user_info.pop('Given Name', None)
        if given_name:
            user_info['given_name'] = given_name
        family_name = user_info.pop('Family Name', None)
        if family_name:
            user_info['family_name'] = family_name
        user_info['name'] = user_info.pop('Name')
        user_info['connection'] = user_info.get('Connection')

        # the ID field needs special processing
        user_id = user_info.pop('Id')
        if user_id.startswith('auth0|'):
            user_id = user_id[6:]
        user_info['id'] = user_id

        if user_info['Connection'] == database_name:
            # This user is stored in the local auth0 DB, and we need to add the password hash
            try:
                password_hash_info = password_hashes_by_email[email]
            except KeyError:
                # Password has is missing, but should have been there
                # Add the user without the password hash.
                users_with_missing_passwords.append(email)
                output.append(user_info)
                continue

            user_info['password_hash'] = password_hash_info['passwordHash']
            output.append(user_info)
        else:
            # This user is authenticated using a non-local store. No password hash expected
            # Do not include them in the output JSON.
            # This tool does not handle social connections or enterprise connections.
            # output.append(user_info)
            continue

    json_output = json.dumps(output, indent=2)
    print(json_output)

    if users_with_missing_passwords:
        print('The following users were missing from the password hash file:', file=sys.stderr)
        for missing_hash_user in users_with_missing_passwords:
            print(missing_hash_user, file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python auth0_import_export.py <users_file_path> <hash_export_file_path>", file=sys.stderr)
        sys.exit(1)

    create_auth0_import(users_file_path=sys.argv[1], hashes_file_path=sys.argv[2])