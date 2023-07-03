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

# set up argparse
def init_argparse():
    # TODO: make "action" flags (list, update, execute, etc.) mutually exclusive
    parser = argparse.ArgumentParser(description='Manage Obsidian settings across multiple vaults.')
    parser.add_argument('--list', '-l', action='store_true', help='list Obsidian vaults')
    parser.add_argument('--update', '-u', help='update Obsidian vaults from UPDATE vault')
    parser.add_argument('--rm', action='store_true', help='with --update, remove .obsidian and create again, rather than retain old .obsidian files')
    parser.add_argument('--execute', '-x', help='run EXECUTE command within each vault (use caution!)')
    parser.add_argument('--backup-list', action='store_true', help='list ISO 8601-formatted .obsidian backup files from all vaults')
    parser.add_argument('--backup-remove', action='store_true', help='remove ISO 8601-formatted .obsidian backup files from all vaults')
    parser.add_argument('--root', default=OBSIDIAN_ROOT_DIR, help=f'Use an alternative Obsidian Root Directory (default {OBSIDIAN_ROOT_DIR!r})')
    parser.add_argument('--version', '-v', action='store_true', help='show version and exit')
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

# helper for `copy_settings()`
# does nothing if `src` does not exist
def copy_settings_file(datestring, src, dest, filename):
    src_target = Path(src) / filename
    dest_target = Path(dest) / filename
    if src_target.exists():
        if dest_target.exists():
            dest_target.rename(str(dest_target)+datestring)
        shutil.copy2(str(src_target), str(dest_target))

# helper for `copy_settings()`
# does nothing if `src` does not exist
def copy_settings_dir(datestring, src, dest, dirname):
    src_target = Path(src) / dirname
    dest_target = Path(dest) / dirname
    if src_target.exists():
        if dest_target.exists():
            dest_target.rename(str(dest_target)+datestring)
        shutil.copytree(str(src_target), dest_target)

# copy the usual settings files from `src` to `dest`
# `dest` is backed up to same filename with a ISO 8601-style
# date string ('2021-05-23T23:38:32.509386Z') in UTC appended,
# unless `--rm` is given
def copy_settings(src, dest, args):
    # don't operate on self
    if str(src) == str(dest):
        return

    print(f"Copying '{src}' configuration to '{dest}'")

    # expand src and dest
    src = Path(src) / '.obsidian'
    dest = Path(dest) / '.obsidian'

    # get current date/time
    datestring = f"-{datetime.datetime.utcnow().isoformat()}Z"

    # if --rm, remove and recreate .obsidian
    if args.rm:
        shutil.rmtree(str(dest), ignore_errors=True)
        dest.mkdir()

    # copy config
    copy_settings_file(datestring, src, dest, 'config')

    # copy starred.json
    copy_settings_file(datestring, src, dest, 'starred.json')

    # copy file used for vaults distributed to others via git
    copy_settings_file(datestring, src, dest, 'README.md')

    # copy plugins
    copy_settings_dir(datestring, src, dest, 'plugins')

    # copy snippets
    copy_settings_dir(datestring, src, dest, 'snippets')

def backup_list_remove(vault_path, args):
    dir_path = Path(vault_path) / '.obsidian'
    iso_8601_glob = '*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9]*Z'
    for dest in dir_path.glob(iso_8601_glob):
        if args.backup_list:
            print(dest)
        elif args.backup_remove:
            if dest.is_file():
                dest.unlink()
            elif dest.is_dir():
                shutil.rmtree(str(dest), ignore_errors=True)

def main():
    # set up argparse
    argparser = init_argparse();
    args = argparser.parse_args();

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
                p = subprocess.Popen(args.execute, cwd=vault_path, shell=True)
                p.wait()
        else:
            argparser.print_help(sys.stderr)

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    exit(main())
