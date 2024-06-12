#!/usr/bin/env -S python -u
# Without -u, output from python is buffered and appears _after_ subprocess output.

################################################################
#
# osm.py - Obsidian Settings Manager
# Copyright 2021-2023 Peter Kaminski. Licensed under MIT License.
# https://github.com/peterkaminski/obsidian-settings-manager
#
################################################################

################################################################
#
# DESIGN GOALS:
#
# As this is a conceptually simple script for copying Obsidian
# vault meta-data between vaults:
#   1. One file that can be copied to where-ever the user wants.
#   2. Default configuration that works out of the box.
#   3. Independent configurtion that the user can choose to set
#      up, regardless of where this script lives or is run from.
#   4. Only use Batteries Included Python libraries so that no
#      additional setup is needed to run this script.
#
# This script operates with two different "configuration files":
#   1. Our own (OSM) configuration:
#      a) Where to find the Obsidian configuration.
#      b) What parts of the vaults should be copied.
#   2. Obsidians configuration.
#      a) The location of the Obsidian vaults and their
#         individual vault-specifc configuration.
#
# CODE STRUCTURE:
#
# To keep this as a single runnable file, rather than having
# separate utility modules, the code is organized into sections:
#
#   - Usual Python header materials
#   - Global Variables
#   - Generic utiltiy functions
#   - Configuration functions
#   - Action functions
#
# DATA STRUCTURES
#
# Configurations:
#   - JSON converted to Python.
# Files To Copy:
#   - A list of actions and their items (see the README)
#   - A set of files to copy(or diff) is constructed from
#     sequentially processing the actions in the configuration.
#   - Each action is mapped to a set function to be applied
#     to the resulting list of files derived from the items.
#   - The items indicate where to find the desired files,
#     with the actual list of files depending on the contents of
#     the source vault at the time of examination.
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

###
# Globals
###

OSM_CONFIG_FILE = 'osm.config'
OSM_CONFIG_ENV_VAR_OVERRIDE = 'OSM_CONFIG_FILE'
OSM_CONFIG = {}  # Will be replaced (using .update()) by the config data we end up loading.
# NOTE: Documented keys in the OSM Config should not start with an underscore (_),
#       as the running code will add new keys with that prefix (using helper functions).
OSM_DEFAULT_CONFIG = r'''
{
    "obsidian_config": {
        "config_file": "obsidian.json",
        "search_path": [
            "/Users/<username>/Library/Application Support/obsidian",
            "/home/<username>/.config/obsidian",
            "/home/<username>/.var/app/md.obsidian.Obsidian/config/obsidian",
            "C:\\Users\\<username>\\AppData\\obsidian"
        ],
        "config_file_override": null
    },
    "files_to_copy": [
        { "copy": "README.md" },
        { "copy": "config" },
        { "copy": "*.json" },
        { "skip": "app.json" },
        { "skip": "core-plugins**" },
        { "skip": "workspace*" },
        { "skip": "command-palette.json" },

        { "copy": "plugins" },
        { "skip": "plugins/auto-note-mover" },

        { "copy": "snippets" },
        { "copy": "themes" }
    ],
    "backup": {
        "archive_format_priority_list": ["zip", "gztar", "bztar", "xztar", "tar"],
        "location": ".osm-obsidian-settings-backup"
    }
}
'''

OBSIDIAN_CONFIG = {}  # Will be .updated() with the obsidian configuration file data.

ACTIONS_TO_TAKE = []  # Will be updated with the file actions are processed from the OSM config.
ITEMS_TO_COPY = []  # Path() file objects; updated when FILE_ACTIONS are applied to a source vault.

def datestring():
    '''Return the current date and time in UTC string format.'''
    return datetime.datetime.utcnow().isoformat() + 'Z'

# Keep this in sync with the format returned by datestring()
ISO_8601_GLOB = '*[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z*'

VERBOSE = False
DRY_RUN = False

# Various 'what went wrong' controls a user can use to see why OSM isn't doing what they expected.
CONFIG_TRACE = os.getenv('CONFIG_TRACE', False)

DIFF_CMD = ''
'''When not '', it is set to the absolute path of the diff command to use.'''

# Map "files_to_copy" actions to functions for managing the set of files to operate on.
FILE_ACTIONS = {
    "copy": set.add,
    "skip": set.discard
}

# Dedup and condense some error message strings.
# Good for humans to read, but clutters up code when they're inline.
BAD_ACTION_MSG = 'is an unknown/invalid action in OSM Configuration in the "files_to_copy" list'
BAD_ITEM_MSG = 'OSM Configuration item (value) in "files_to_copy" list:'

###
# Generic Utility Functions
###

def config_trace(*args, **kwargs):
    '''Print parameters if CONFIG_TRACE flag is True.'''
    if CONFIG_TRACE:
        print(*args, **kwargs)

def verbose(*args, **kwargs):
    '''Print parameters if VERBOSE flag is True or DRY_RUN is True.'''
    if DRY_RUN:
        print('DRY-RUN:' if args else '', *args, **kwargs)
    elif VERBOSE:
        print(*args, **kwargs)

def must_get_key(a_dict, key, aux_msg):
    '''Return the value of key from a_dict, or print an descriptive error message and exit.'''
    try:
        return a_dict[key]
    except Exception:
        print(f'Error, missing key {key!r} {aux_msg}')
        exit(-1)

def must_be_type(item, type_, prefix_msg):
    '''If item is an instance of type_, return it for convenience, or print a descriptive error message and exit.'''
    if isinstance(item, type_):
        return item
    print(f'Error: {prefix_msg} {type(item).__name__}: {item!r} is not a {type_.__name__}')
    exit(-1)


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

def init_argparse():
    '''Return an initialized command line parser.'''
    parser = argparse.ArgumentParser(description='Manage Obsidian settings across multiple vaults.')
    parser.add_argument('--verbose', action='store_true', help='Print what the file system operations are happening')
    parser.add_argument('--dry-run', '-n', action='store_true', help='Do a dry-run. Show what would be done, without doing it.')
    parser.add_argument('--config', '-c', help="Use CONFIG as the OSM config file instead of the default")
    only_one_of = parser.add_mutually_exclusive_group(required=True)
    only_one_of.add_argument('--list', '-l', action='store_true', help='list Obsidian vaults')
    only_one_of.add_argument('--update', '-u', help='update Obsidian vaults from UPDATE vault')
    only_one_of.add_argument('--exact-copy-of', help='delete and recreate Obsidian vaults with an exact copy of the EXACT_COPY_OF vault')
    only_one_of.add_argument('--diff-to', '-d', help='Like update but instead of copying, just show a diff against DIFF_TO instead (no changes made).')
    only_one_of.add_argument('--execute', '-x', help='run EXECUTE command within each vault (use caution!)')
    only_one_of.add_argument('--backup-all-vaults', action="store_true", help='make a backup of the obsidian settings for all vaults')
    only_one_of.add_argument('--backup-vault', help='make a backup of the obsidian settings for BACKUP_VAULT')
    only_one_of.add_argument('--backup-list', action='store_true', help='list ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--backup-remove', action='store_true', help='remove ISO 8601-formatted .obsidian backup files from all vaults')
    only_one_of.add_argument('--show-selected', dest="from_vault", help='print the files that would be copied from FROM_VAULT to other vaults, then exit')
    only_one_of.add_argument('--print-default-config', action='store_true', help='print the default configuration and extt')
    only_one_of.add_argument('--version', '-v', action='store_true', help='show version and exit')
    return parser

def only_relative_files_from(item_list, relative_to):
    '''Return a list of just the files from item_list.'''
    return [item.relative_to(relative_to) for item in item_list if item.is_file()]

def get_matching_files(source_dir, item):
    '''
    Returns a list of relative Path objects for all the files described by item.

    Files are a list of themselves.
    Directories are the list of files in them, recursively.
    Globs are whatever files match the glob, if any.
    '''
    item_path = source_dir / item
    if item_path.is_file():
        return [Path(item)]
    if item_path.is_dir():
        return only_relative_files_from(item_path.rglob('*'), source_dir)
    return only_relative_files_from(source_dir.glob(item), source_dir)

def process_action_list_in(source_dir, actions_list):
    '''Return a list of Path files to copy by applying the actions list actions to source_dir.'''
    files = set()
    source_dir = Path(source_dir)
    for action, item in actions_list:
        for a_file in get_matching_files(source_dir, item):
            action(files, a_file)
    return files

###
# Configuration Functions - OSM
###

def remember_obsidian_root_dir(value):
    '''Keep track of where the Obsidian root directory was by adding it to our config.'''
    OSM_CONFIG['_obsidian_root_dir'] = value

def get_obsidian_root_dir():
    '''Return the Obsidian root directory saved in our config.'''
    return OSM_CONFIG['_obsidian_root_dir']

def find_osm_config_file():
    '''Return the first OSM config file we find from our priority list, or None.'''
    env_var_value = os.getenv(OSM_CONFIG_ENV_VAR_OVERRIDE)
    config_trace(f'OSM Config checking environment variable: {env_var_value!r}')
    if env_var_value:
        return Path(env_var_value).expanduser()

    local_config = Path(OSM_CONFIG_FILE)
    config_trace(f'OSM Config checking local directory: {local_config}')
    if local_config.is_file():
        return local_config

    home_config = Path.home() / OSM_CONFIG_FILE
    config_trace(f'OSM Config checking home directory: {home_config}')
    if home_config.is_file():
        return home_config

    config_trace('OSM Config not found')
    return None

def load_osm_config(config_file=None):
    '''Load our OSM configuration from the config_file if given, or from our hierarchy of places to look.'''
    config_file = config_file or find_osm_config_file()
    if config_file:
        config_trace(f'Loading OSM configuration from: {config_file}')
        OSM_CONFIG.update(safe_load_json(safe_read_contents(config_file), f'Config file: {config_file}'))
    else:
        config_trace('Loading OSM configuration from internal default configuration')
        OSM_CONFIG.update(safe_load_json(OSM_DEFAULT_CONFIG, 'Built-in configuration data'))

def get_processing_directives():
    '''
    Yield a series of (function, item) pairs from the files to copy from a source vault.

    If there are any errors in the config file, print a descriptive error message and exit.
    Each returned function should be called with a set and a filename.
    '''
    directives = must_get_key(OSM_CONFIG, 'files_to_copy', 'in OSM configuration')
    must_be_type(directives, list, 'OSM Configuration key "files_to_copy"')

    for directive in directives:
        must_be_type(directive, dict, 'OSM Configuration value under "files_to_copy"')
        # Having more than one action type per step seems confusing, so limit to just 1.
        if len(directive) != 1:
            print(f'Error: OSM Configuration list elements under "files_to_copy" must have only one key: {directive!r}')
            exit(-1)
        for action, item in directive.items():  # Easiest way to access the contents even when there is only one key/value pair.
            # Actions must be strings to pass JSON parsing, not checking their type here.
            operation = must_get_key(FILE_ACTIONS, action, BAD_ACTION_MSG)
            yield (operation, must_be_type(item, str, BAD_ITEM_MSG))

def get_items_to_copy(src):
    '''
    Return the list of Paths to be copied from src.

    The return value is also cached in the ITEMS_TO_COPY list so we only build the list once.
    '''
    if not ITEMS_TO_COPY:
        ITEMS_TO_COPY.extend(sorted(process_action_list_in(src, ACTIONS_TO_TAKE)))
    return ITEMS_TO_COPY

###
# Configuration Functions - Obsidian
###

def find_obsidian_config_file():
    '''Return the Path for the Obsidian config file from our configuration, or print an error message and exit if not found.'''
    obsidian_config = must_get_key(OSM_CONFIG, 'obsidian_config', 'from top level OSM configuration file')
    config_file_name = obsidian_config.get('config_file_override')
    if config_file_name:
        config_file = Path(config_file_name).expanduser()
        if config_file.is_file():
            return config_file
        print(f'Unable to find Obsidian configuration file: {config_file_name!r}')
        print("from the 'config_file_override' configuration value.")
        exit(-1)
    config_file_base_name = must_get_key(obsidian_config, 'config_file', 'from the obsdian_config part of the OSM configuration file')
    config_file_search_path = must_get_key(obsidian_config, 'search_path', 'from the obsdian_config part of the OSM configuration file')
    username = os.getlogin()
    checked_files = []
    for a_dir in config_file_search_path:
        candidate = Path(a_dir.replace("<username>", username)) / config_file_base_name
        checked_files.append(candidate)
        if candidate.is_file():
            config_trace('Found Obsidian config file:', candidate)
            return candidate
    print("Error, could not locate Obsidian configuration file after checking all of:")
    print("\n".join(map(str, checked_files)))
    exit(-1)

def load_obsidian_config():
    '''Find and load the obsidian config file after having loaded our own config file.'''
    config_file = find_obsidian_config_file()
    config_trace("Loading Obsidian configuration from", config_file)
    remember_obsidian_root_dir(config_file.parent)
    OBSIDIAN_CONFIG.update(safe_load_json(safe_read_contents(config_file), f'Obsidian config file: {config_file}'))

def user_vault_paths(root_dir):
    '''Return the paths for each vault in obsidian that isn't a system vault.'''
    # The vaults' dictionary's keys aren't of any use/interest to us,
    # so we only need to look the path defined in the vault.
    return [vault_data['path'] for vault_data in OBSIDIAN_CONFIG['vaults'].values()
            if is_user_path(root_dir, vault_data['path'])]

def get_vault_paths():
    '''
    Return a list of all the vault paths Obsidian is tracking.

    The list is string version of the absolute paths for the the vaults.
    '''
    return sorted(user_vault_paths(get_obsidian_root_dir()), key=str.lower)

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

###
# Action Functions
###

def print_default_config():
    '''Print the default configuration so user can save and customize.'''
    print(OSM_DEFAULT_CONFIG)

def show_selected_files_for(vault):
    '''Print the files that would be copied from vault.'''
    print("These files would be copied from", vault)
    for a_file in get_items_to_copy(Path(vault) / '.obsidian'):
        print("   ", a_file)

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

def copy_settings_item(src, dest, itemname):
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

    backup_vault(dest)

    src = src / '.obsidian'
    dest = dest / '.obsidian'

    if clean_first:
        recreate_dir(dest)

    for item in get_items_to_copy(src):
        copy_settings_item(src, dest, item)

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

    for item in get_items_to_copy(src):
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


def backup_vault(vault_path):
    print(f'# Backing up settings for: {vault_path}')

    vault_path = Path(vault_path)

    backup_info = must_get_key(OSM_CONFIG, 'backup', 'in OSM configuration')
    backup_dir_name = Path(must_get_key(backup_info, 'location', 'in "backup" section of OSM configuration'))
    backup_formats = must_get_key(backup_info, 'archive_format_priority_list', 'in "backup" section of OSM configuration')

    backup_from_dir = vault_path / '.obsidian'
    backup_full_dir = Path(vault_path) / backup_dir_name
    backup_full_dir.mkdir(exist_ok=True)
    backup_file = Path(vault_path) / backup_dir_name / datestring()
    for backup_format in backup_formats:
        try:
            backup_file = shutil.make_archive(backup_file, backup_format, root_dir=backup_from_dir, dry_run=DRY_RUN)
            if backup_file:
                verbose("Backup file:", backup_file)
                verbose()
                return
        except ValueError:
            pass  # Not a supported format, keep checking.

    print("Unable to make backup of", vault_path, "in any format:", ", ".join(map(repr, backup_formats)))
    exit(-1)

def backup_operation(vault_path, operation):
    '''Call operation with each backup item found in the given vault.'''
    backup_info = must_get_key(OSM_CONFIG, 'backup', 'in OSM configuration')
    backup_dir = Path(must_get_key(backup_info, 'location', 'in "backup" section of OSM configuration'))

    print(f'# {vault_path}')
    dir_path = Path(vault_path) / backup_dir
    for dest in dir_path.glob(ISO_8601_GLOB):
        operation(dest)
    print()

def show_vault_path(vault_path):
    '''Print the vault path relative to the user's home directory (more readable).'''
    print(Path(vault_path).relative_to(Path.home()))

###
# MAIN
###

def main():
    argparser = init_argparse()
    args = argparser.parse_args()

    if args.verbose:
        global VERBOSE
        VERBOSE = True

    if args.dry_run:
        global DRY_RUN
        DRY_RUN = True

    if args.version:
        print(f'{APPNAME} {VERSION}')
        return

    if args.print_default_config:
        print_default_config()
        return

    if args.diff_to:
        global DIFF_CMD
        DIFF_CMD = shutil.which('diff')
        if not DIFF_CMD:
            print("Error: Cannot locate the 'diff' command, aborting.")
            exit(-1)

    load_osm_config(args.config)
    load_obsidian_config()

    try:
        vault_paths = get_vault_paths()
        ACTIONS_TO_TAKE.extend(get_processing_directives())

        if args.list:
            call_for_each_vault(vault_paths, show_vault_path)
        elif args.from_vault:
            ensure_valid_vault(vault_paths, args.from_vault)
            show_selected_files_for(Path.home() / args.from_vault)
        elif args.update:
            ensure_valid_vault(vault_paths, args.update)
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.update, clean_first=False)
        elif args.exact_copy_of:
            ensure_valid_vault(vault_paths, args.exact_copy_of)
            call_for_each_vault(vault_paths, copy_settings, Path.home() / args.exact_copy_of, clean_first=True)
        elif args.diff_to:
            ensure_valid_vault(vault_paths, args.diff_to)
            call_for_each_vault(vault_paths, diff_settings, Path.home() / args.diff_to)
        elif args.backup_all_vaults:
            call_for_each_vault(vault_paths, backup_vault)
        elif args.backup_vault:
            ensure_valid_vault(vault_paths, args.backup_vault)
            backup_vault(Path.home() / args.backup_vault)
        elif args.backup_list:
            call_for_each_vault(vault_paths, backup_operation, print)
        elif args.backup_remove:
            call_for_each_vault(vault_paths, backup_operation, remove_item)
        elif args.execute:
            call_for_each_vault(vault_paths, execute_command, args.execute)
        else:
            argparser.print_help(sys.stderr)

    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    exit(main())
