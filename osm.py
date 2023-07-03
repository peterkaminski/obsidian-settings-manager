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
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

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
    parser.add_argument('--version', '-v', action='store_true', help='show version and exit')
    return parser

# find all the vaults Obsidian is tracking
def get_vault_paths():
    vault_paths = []

    # read primary file
    # location per https://help.obsidian.md/Advanced+topics/How+Obsidian+stores+data#System+directory
    # (TODO: should be parameterized and support other OSes)
    with open(Path.home() / 'Library/Application Support/obsidian/obsidian.json') as infile:
        obsidian = json.load(infile)
        vaults = obsidian['vaults']
        for vault in vaults:
            # skip Help or other system directory vaults
            # TODO: support other OSes
            if Path(vaults[vault]['path']).parent == Path.home() / 'Library/Application Support/obsidian':
                continue
            vault_paths.append(vaults[vault]['path'])

        # sort paths (case-insensitive)
        vault_paths.sort(key=str.lower)

    # return paths
    return vault_paths

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
        vault_paths = get_vault_paths()

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
