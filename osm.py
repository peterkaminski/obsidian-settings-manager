#!/usr/bin/env -S python -u
# Without -u, output from python is buffered and appears _after_ subprocess output.

################################################################
#
# osm.py - Obsidian Settings Manager
# Copyright 2021-2023 Peter Kaminski. Licensed under MIT License.
# https://github.com/peterkaminski/obsidian-settings-manager
#
################################################################

VERSION = 'v0.3.2'
APPNAME = 'Obsidian Settings Manager'

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

DEFAULT_OBSIDIAN_ROOT = str(Path.home() / 'Library' / 'Application Support' / 'obsidian')
OBSIDIAN_ROOT_DIR = os.getenv('OBSIDIAN_ROOT', DEFAULT_OBSIDIAN_ROOT)

ITEMS_TO_COPY = [
    'config',
    'starred.json',
    'README.md',  # used for vaults distributed to others via git
    'plugins',
    'snippets',
]

def datestring():
    '''Return the current date and time in UTC string format.'''
    return f'-{datetime.datetime.utcnow().isoformat()}Z'

# Keep this in sync with the format returned by datestring()
ISO_8601_GLOB = '*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'


VERBOSE = False

DRY_RUN = False

DIFF_CMD = ''
'''When not '', it is set to the absolute path of the diff command to use.'''

def verbose(*args, **kwargs):
    '''Print parameters if VERBOSE flag is True or DRY_RUN is True.'''
    if DRY_RUN:
        print('DRY-RUN:' if args else '', *args, **kwargs)
    elif VERBOSE:
        print(*args, **kwargs)

def init_argparse():
    '''Return an initialized command line parser.'''
    parser = argparse.ArgumentParser(description='Manage Obsidian settings across multiple vaults.')
    parser.add_argument('--verbose', action='store_true', help='Print what the file system operations are happening')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Do a dry-run. Show what would be done, without doing it.')
    parser.add_argument('--root', default=OBSIDIAN_ROOT_DIR, help=f'Use an alternative Obsidian Root Directory (default {OBSIDIAN_ROOT_DIR!r})')
    only_one_of = parser.add_mutually_exclusive_group(required=True)
    only_one_of.add_argument('--list', '-l', action='store_true', help='list Obsidian vaults')
    only_one_of.add_argument('--update', '-u', help='update Obsidian vaults from UPDATE vault')
    only_one_of.add_argument('--exact-copy-of', help='delete and recreate Obsidian vaults with an exact copy of the EXACT_COPY_OF vault')
    only_one_of.add_argument('--diff-to', '-d', help='Like update but instead of copying, just show a diff against DIFF_TO instead (no changes made).')
    only_one_of.add_argument('--execute', '-x', help='run EXECUTE command within each vault (use caution!)')
    only_one_of.add_argument('--backup-list', action='store_true', help='list ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--backup-remove', action='store_true', help='remove ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--version', '-v', action='store_true', help='show version and exit')
    return parser

def safe_read_contents(from_file):
    '''Return the contents of from_file, or exit with an error message if open/read fails.'''
    try:
        return Path(from_file).read_text()
    except Exception as e:
        print('Unable to read file:', from_file)
        print(e)
        exit(-1)

def safe_load_json(from_contents, source):
    '''Return the parsed JSON from_contents, or exit with an error message if the parse fails.'''
    try:
        return json.loads(from_contents)
    except Exception as e:
        print('Unable to parse json from', source)
        print(e)
        exit(-1)

def is_user_path(root_dir, path_to_test):
    '''Return True if path_to_test is a user's path, not an Obsidian system path (such as Help, etc)'''
    return Path(path_to_test).parent != root_dir

def user_vault_paths_from(obsidian, root_dir):
    '''Return the paths for each vault in obsidian that isn't a system vault.'''
    # The vaults' dictionary's keys aren't of any use/interest to us,
    # so we only need to look the path defined in the vault.
    return [vault_data['path'] for vault_data in obsidian['vaults'].values()
            if is_user_path(root_dir, vault_data['path'])]

def get_vault_paths(root_dir):
    '''
    Return a list of all the vault paths Obsidian is tracking.

    The list is string version of the absolute paths for the the vaults.
    '''
    root_dir = Path(root_dir)
    obsidian_config = root_dir / 'obsidian.json'
    obsidian = safe_load_json(safe_read_contents(obsidian_config), f'Obsidian config file: {obsidian_config}')
    return sorted(user_vault_paths_from(obsidian, root_dir), key=str.lower)

# It might be cleaner to have this defined after the functions it calls,
# but keeping it close to get_vault_paths to make it easier to track changes if needed.
def ensure_valid_vault(vault_paths, vault_to_check):
    '''
    Ensure that vault_to_check (relative path) is in the list of (absolute path) vault_paths.

    Only returns if it is, otherwise, print an error and exit.
    '''
    if str(Path.home() / vault_to_check) in vault_paths:
        return
    print(f'Error: {vault_to_check!r} is not one of your vaults:')
    call_for_each_vault(vault_paths, show_vault_path)
    exit(-1)

def call_for_each_vault(vault_paths, operation, *args, **kwargs):
    '''Call operation with each vault in vault_paths, followed by *args and **kwargs.'''
    for vault_path in vault_paths:
        operation(vault_path, *args, **kwargs)

def backup(item, suffix):
    '''Rename item to have the given suffix.'''
    backup = str(item)+suffix
    verbose('Saving current', item, 'as', backup)
    if DRY_RUN:
        return
    item.rename(backup)

def copy_directory(src_target, dest_target):
    '''Copy the src_target directry to dest_target.'''
    verbose('Copying directory', src_target, 'to', dest_target)
    if DRY_RUN:
        return
    shutil.copytree(src_target, dest_target)

def copy_file(src_target, dest_target):
    '''Copy the src_target file to dest_target.'''
    verbose('Copying file', src_target, 'to', dest_target)
    if DRY_RUN:
        return
    shutil.copy2(src_target, dest_target)

def recreate_dir(dest):
    '''Delete and recreate the given directory.'''
    verbose('Removing and recreating', dest)
    if DRY_RUN:
        return
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir()

def remove_item(dest):
    '''Remove the given item (file or directory).'''
    is_dir = dest.is_dir()
    verbose('Removing backup', 'directory' if is_dir else 'file', dest)
    if DRY_RUN:
        return
    if is_dir:
        shutil.rmtree(dest, ignore_errors=True)
    else:
        dest.unlink()

def execute_command(vault_path, command):
    '''Execute the given command in the given vault_path.'''
    print(f'\n# {vault_path}\n')
    if DRY_RUN:
        verbose('Would run command:', repr(command))
    else:
        subprocess.run(command, cwd=vault_path, shell=True)

def copy_settings_item(suffix, src, dest, itemname):
    '''
    Copy itemname from src to dest.

    itemname can be a file or a directory, if a directory it is recursively copied.
    If itemname already exists in dest, it is renamed with suffix appended.
    If itemname does not exist in src, nothing is done.
    '''

    src_target = Path(src) / itemname
    dest_target = Path(dest) / itemname
    if not src_target.exists():
        return
    verbose()
    if dest_target.exists():
        backup(dest_target, suffix)
    if src_target.is_dir():
        copy_directory(src_target, dest_target)
    else:
        copy_file(src_target, dest_target)

def copy_settings(dest, src, clean_first=False):
    '''
    Copy the usual settings items into dest vault from src.

    Items in `dest` are backed up to their same name with a ISO 8601-style
    date string ('2021-05-23T23:38:32.509386Z') in UTC appended,
    unless clean_first is True. (clean_first means everthing in dest's settings
    is deleted so there is nothing to back up.)
    '''
    src = Path(src)
    dest = Path(dest)
    # don't operate on self
    if src.samefile(dest):
        return

    print(f"Copying '{src}' configuration to '{dest}'")

    src = src / '.obsidian'
    dest = dest / '.obsidian'

    # Use a timestamp for the suffix for uniqueness
    suffix = datestring()

    if clean_first:
        recreate_dir(dest)

    for item in ITEMS_TO_COPY:
        copy_settings_item(suffix, src, dest, item)

def do_diff(old, new):
    '''Diff two items, prefix with the diff command used.'''
    diff_cmd = [DIFF_CMD]
    if old.is_dir():
        diff_cmd.append('-r')
    diff_cmd += [old, new]
    print(*diff_cmd)
    if DRY_RUN:
        return
    subprocess.run(diff_cmd)

def diff_settings(dest, src):
    '''
    Diff the settings between src and dest that would be updated if udpate were used.

    Note that the diffs are done between dest and src to show src as "the new" stuff.
    '''
    src = Path(src)
    dest = Path(dest)
    # don't compre to self
    if src.samefile(dest):
        return

    print(f"\n# Diffing '{dest}' configuration to '{src}'")

    src = src / '.obsidian'
    dest = dest / '.obsidian'

    for item in ITEMS_TO_COPY:
        dest_item = dest / item
        src_item = src / item
        if src_item.exists() and dest_item.exists():
            print()
            do_diff(dest_item, src_item)
        elif src_item.exists():
            print(f"\n## '{dest_item}' doesn't exist; it would be copied from '{src_item}' on '--update'.")
        elif dest_item.exists():
            print(f"\n## '{dest_item}' would be removed with `--update --rm` because '{src_item}' doesn't exist.")
        # If neither exist, nothing to do, nothing to say. Move along.


def backup_list_operation(vault_path, operation):
    '''Call operation with each backup item found in the given vault.'''
    dir_path = Path(vault_path) / '.obsidian'
    for dest in dir_path.glob(ISO_8601_GLOB):
        operation(dest)

def show_vault_path(vault_path):
    '''Print the vault path relative to the user's home directory (more readable).'''
    print(Path(vault_path).relative_to(Path.home()))

def main():
    argparser = init_argparse()
    args = argparser.parse_args()

    if args.verbose:
        global VERBOSE
        VERBOSE = True

    if args.dry_run:
        global DRY_RUN
        DRY_RUN = True

    if args.diff_to:
        global DIFF_CMD
        DIFF_CMD = shutil.which('diff')
        if not DIFF_CMD:
            print("Error: Cannot locate the 'diff' command, aborting.")
            exit(-1)

    try:
        vault_paths = get_vault_paths(args.root)

        if args.version:
            print(f'{APPNAME} {VERSION}')
        elif args.list:
            call_for_each_vault(vault_paths, show_vault_path)
        elif args.update:
            ensure_valid_vault(vault_paths, args.update)
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.update, clean_first=False)
        elif args.exact_copy_of:
            ensure_valid_vault(vault_paths, args.exact_copy_of)
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.exact_copy_of, clean_first=True)
        elif args.diff_to:
            ensure_valid_vault(vault_paths, args.diff_to)
            call_for_each_vault(vault_paths, diff_settings, Path.home() / args.diff_to)
        elif args.backup_list:
            call_for_each_vault(vault_paths, backup_list_operation, print)
        elif args.backup_remove:
            call_for_each_vault(vault_paths, backup_list_operation, remove_item)
        elif args.execute:
            call_for_each_vault(vault_paths, execute_command, args.execute)
        else:
            argparser.print_help(sys.stderr)

    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    exit(main())
