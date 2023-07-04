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
OBSIDIAN_ROOT_DIR = os.getenv("OBSIDIAN_ROOT", DEFAULT_OBSIDIAN_ROOT)

ITEMS_TO_COPY = [
    'config',
    'starred.json',
    'README.md', # used for vaults distributed to others via git
    'plugins',
    'snippets',
]

def datestring():
    """Return the current date and time in UTC string format."""
    return f'-{datetime.datetime.utcnow().isoformat()}Z'

# Keep this in sync with the format returned by datestring()
ISO_8601_GLOB = '*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9]*Z'


VERBOSE = False

DRY_RUN = False

def verbose(*args, **kwargs):
    """Print parameters if VERBOSE flag is True or DRY_RUN is True."""
    if DRY_RUN:
        print('DRY-RUN:' if args else '', *args, **kwargs)
    elif VERBOSE:
        print(*args, **kwargs)

# set up argparse
def init_argparse():
    parser = argparse.ArgumentParser(description='Manage Obsidian settings across multiple vaults.')
    parser.add_argument('--verbose', action='store_true', help='Print what the file system operations are happening')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Do a dry-run. Show what would be done, without doing it.')
    parser.add_argument('--root', default=OBSIDIAN_ROOT_DIR, help=f'Use an alternative Obsidian Root Directory (default {OBSIDIAN_ROOT_DIR!r})')
    parser.add_argument('--rm', action='store_true', help='with --update, remove .obsidian and create again, rather than retain old .obsidian files')
    only_one_of = parser.add_mutually_exclusive_group(required=True)
    only_one_of.add_argument('--list', '-l', action='store_true', help='list Obsidian vaults')
    only_one_of.add_argument('--update', '-u', help='update Obsidian vaults from UPDATE vault')
    only_one_of.add_argument('--execute', '-x', help='run EXECUTE command within each vault (use caution!)')
    only_one_of.add_argument('--backup-list', action='store_true', help='list ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--backup-remove', action='store_true', help='remove ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--version', '-v', action='store_true', help='show version and exit')
    return parser

def safe_load_config(config_file):
    """Return the parsed JSON from config_file, or exit with an error message if open/parse fails."""
    try:
        with open(config_file) as infile:
            return json.load(infile)
    except Exception as e:
        print('Unable to load Obsidian config file:', config_file)
        print(e)
        exit(-1)

def is_user_path(root_dir, path_to_test):
    """Return True if path_to_test is a user's path, not an Obsidian system path (such as Help, etc)"""
    return Path(path_to_test).parent != root_dir

def user_vault_paths_from(obsidian, root_dir):
    """Return the paths for each vault in obsidian that isn't a system vault."""
    # The vaults' dictionary's keys aren't of any use/interest to us,
    # so we only need to look the path defined in the vault.
    return [vault_data['path'] for vault_data in obsidian['vaults'].values()
            if is_user_path(root_dir, vault_data['path'])]
    
# find all the vaults Obsidian is tracking
def get_vault_paths(root_dir):
    root_dir = Path(root_dir)
    obsidian = safe_load_config(root_dir / 'obsidian.json')
    return sorted(user_vault_paths_from(obsidian, root_dir), key=str.lower)

def backup(item, suffix):
    """Rename item to have the given suffix."""
    backup = str(item)+suffix
    verbose("Saving current", item, "as", backup)
    if DRY_RUN:
        return
    item.rename(backup)

def copy_directory(src_target, dest_target):
    """Copy the src_target directry to dest_target."""
    verbose("Copying directory", src_target, "to", dest_target)
    if DRY_RUN:
        return
    shutil.copytree(src_target, dest_target)

def copy_file(src_target, dest_target):
    """Copy the src_target file to dest_target."""
    verbose("Copying file", src_target, "to", dest_target)
    if DRY_RUN:
        return
    shutil.copy2(src_target, dest_target)

def recreate_dir(dest):
    """Delete and recreate the given directory."""
    verbose("Removing and recreating", dest)
    if DRY_RUN:
        return
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir()

def remove_item(dest):
    """Remove the given item (file or directory)."""
    is_dir = dest.is_dir()
    verbose("Removing backup", "directory" if is_dir else "file", dest)
    if DRY_RUN:
        return
    if is_dir:
        shutil.rmtree(dest, ignore_errors=True)
    else:
        dest.unlink()

def execute_command(command, vault_path):
    """Execute the given command in the given vault_path."""
    if DRY_RUN:
        verbose("Would run command:", repr(command))
    else:
        subprocess.run(command, cwd=vault_path, shell=True)

def copy_settings_item(suffix, src, dest, itemname):
    """
    Copy itemname from src to dest.

    itemname can be a file or a directory, if a directory it is recursively copied.
    If itemname already exists in dest, it is renamed with suffix appended.
    If itemname does not exist in src, nothing is done.
    """

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

# copy the usual settings files from `src` to `dest`
# `dest` is backed up to same filename with a ISO 8601-style
# date string ('2021-05-23T23:38:32.509386Z') in UTC appended,
# unless `--rm` is given
def copy_settings(src, dest, args):
    src = Path(src)
    dest = Path(dest)
    # don't operate on self
    if src.samefile(dest):
        return

    print(f"Copying '{src}' configuration to '{dest}'")

    # expand src and dest
    src = src / '.obsidian'
    dest = dest / '.obsidian'

    # Use a timestamp for the suffix for uniqueness
    suffix = datestring()

    # if --rm, remove and recreate .obsidian
    if args.rm:
        recreate_dir(dest)

    for item in ITEMS_TO_COPY:
        copy_settings_item(suffix, src, dest, item)

def backup_list_remove(vault_path, args):
    dir_path = Path(vault_path) / '.obsidian'
    for dest in dir_path.glob(ISO_8601_GLOB):
        if args.backup_list:
            print(dest)
        elif args.backup_remove:
            remove_item(dest)

def main():
    # set up argparse
    argparser = init_argparse();
    args = argparser.parse_args();

    if args.verbose:
        global VERBOSE
        VERBOSE = True

    if args.dry_run:
        global DRY_RUN
        DRY_RUN = True

    # do stuff
    try:
        vault_paths = get_vault_paths(args.root)

        # decide what to do
        if args.version:
            print(f'{APPNAME} {VERSION}')
        elif args.list:
            for vault_path in vault_paths:
                print(Path(vault_path).relative_to(Path.home()))
        elif args.update:
            # TODO: check if given UPDATE vault is really an Obsidian vault
            for vault_path in vault_paths:
                copy_settings(Path.home() / args.update, vault_path, args)
        elif args.backup_list or args.backup_remove:
            for vault_path in vault_paths:
                backup_list_remove(vault_path, args)
        elif args.execute:
            for vault_path in vault_paths:
                print(f'\n# {vault_path}\n')
                execute_command(args.execute, vault_path)
        else:
            argparser.print_help(sys.stderr)

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    exit(main())
