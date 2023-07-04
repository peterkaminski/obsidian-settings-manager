#!/usr/bin/env python

################################################################
#
# osm.py - Obsidian Settings Manager
# Copyright 2021 Peter Kaminski. Licensed under MIT License.
# https://github.com/peterkaminski/obsidian-settings-manager
#
################################################################

VERSION = 'v0.3.1'
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
ISO_8601_GLOB = '*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9]*Z'


VERBOSE = False

DRY_RUN = False

DIFF_CMD = ''
'''
When not '', it is set to the absolute path of the diff command to use
and the copy commands used by `update` will do a diff instead.
'''

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
    parser.add_argument('--rm', action='store_true', help='with --update, remove .obsidian and create again, rather than retain old .obsidian files')
    only_one_of = parser.add_mutually_exclusive_group(required=True)
    only_one_of.add_argument('--list', '-l', action='store_true', help='list Obsidian vaults')
    only_one_of.add_argument('--update', '-u', help='update Obsidian vaults from UPDATE vault')
    only_one_of.add_argument('--diff-to', '-d', help='Like update but instead of copying, just show a diff against DIFF_TO instead (no changes made).')
    only_one_of.add_argument('--execute', '-x', help='run EXECUTE command within each vault (use caution!)')
    only_one_of.add_argument('--backup-list', action='store_true', help='list ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--backup-remove', action='store_true', help='remove ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--version', '-v', action='store_true', help='show version and exit')
    return parser

def safe_load_config(config_file):
    '''Return the parsed JSON from config_file, or exit with an error message if open/parse fails.'''
    try:
        with open(config_file) as infile:
            return json.load(infile)
    except Exception as e:
        print('Unable to load Obsidian config file:', config_file)
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
    Return a list of all the vault paths Obsidian is trackig.

    The list is string version of the absolute paths for the the vaults.
    '''
    root_dir = Path(root_dir)
    obsidian = safe_load_config(root_dir / 'obsidian.json')
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

def call_for_each_vault(vault_paths, operation, *args):
    '''Call operation with each vault in vault_paths, followed by *args.'''
    for vault_path in vault_paths:
        operation(vault_path, *args)

def backup(item, suffix):
    '''Rename item to have the given suffix.'''
    if DIFF_CMD:
        return
    backup = str(item)+suffix
    verbose('Saving current', item, 'as', backup)
    if DRY_RUN:
        return
    item.rename(backup)

def copy_directory(src_target, dest_target):
    '''Copy the src_target directry to dest_target.'''
    msg = 'Diffing' if DIFF_CMD else 'Copying'
    verbose(msg, 'directory', src_target, 'to', dest_target)
    if DRY_RUN:
        return
    if DIFF_CMD:
        subprocess.run([DIFF_CMD, '-r', src_target, dest_target])
    else:
        shutil.copytree(src_target, dest_target)

def copy_file(src_target, dest_target):
    '''Copy the src_target file to dest_target.'''
    msg = 'Diffing' if DIFF_CMD else 'Copying'
    verbose(msg, 'file', src_target, 'to', dest_target)
    if DRY_RUN:
        return
    if DIFF_CMD:
        subprocess.run([DIFF_CMD, src_target, dest_target])
    else:
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

def copy_settings(dest, src, clean_first):
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

    msg = 'Diffing' if DIFF_CMD else 'Copying'
    print(f"{msg} '{src}' configuration to '{dest}'")

    src = src / '.obsidian'
    dest = dest / '.obsidian'

    # Use a timestamp for the suffix for uniqueness
    suffix = datestring()

    if clean_first:
        recreate_dir(dest)

    for item in ITEMS_TO_COPY:
        copy_settings_item(suffix, src, dest, item)

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
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.update, args.rm)
        elif args.diff_to:
            ensure_valid_vault(vault_paths, args.diff_to)
            # Note: By setting DIFF_CMD above, we can re-use the copy_settings helper.
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.diff_to, False)
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
