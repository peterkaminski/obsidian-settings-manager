# Obsidian Settings Manager v0.3.0

## WARNING AND DISCLAIMER

WARNING: This utility manipulates files in all vaults that Obsidian knows about. It is written to only fiddle with the files in .obsidian (and with the `--rm` flag, to delete the `.obsidian` directory and recreate it), and it is intended to be safe to use. HOWEVER, it is possible that unintentional data loss may occur, and so you should only use this utility if you have backups of all your files, and only if you understand the risks associated with using this utility.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

See LICENSE file for copyright license.

## Overview

This utility helps you manage [Obsidian](https://obsidian.md) settings (including plugins and snippets) across multiple vaults.

In the current incarnation, it can:

- List the vaults Obsidian knows about.
- Copy the settings, plugins, and snippets from one vault to all the other vaults.
- Execute a command within each vault.
- List or remove backup files from the `.obsidian` directory.

Current notes and limitations:

- Early release, no significant testing yet.
- No options for specifying particular destination directories to copy to or to ignore.  In future versions, there may be more options providing more fine-grained control.
- No options for changing which files and directories are copied and which are ignored.  In future versions, there may be more options providing more fine-grained control.
- Mac only (although Windows and Linux wouldn't be too hard).
- Command-line only.
- Python 3 (tested with Python 3.8).

## Installation

Download the repository to your computer.

Create a `venv` directory and activate it.

``` shell
python3 -m venv venv
source venv/bin/activate
```

Install dependencies.

```shell
pip install -r requirements.txt
```

## Operation

### Help

To run the utility:

```shell
./osm.py
```

Try it now.  With no arguments, or with `-h` or `--help`, a short usage summary is printed.

### Show Version

To show the version of the application, use `-v` or `--version`:

```shell
./osm.py -v
```

### List Vaults

To list Obsidian vaults, use `-l` or `--list`:

```shell
./osm.py --list
```

### Update Vault Configuration

To copy this files and directories from one Obsidian's `.obsidian` directory to all the other vaults, use `-u` or `--update`, with the directory name of the source vault after the flag:

```shell
./osm.py --update Vaults/obsidian-settings
```

In this example, there is an Obsidian vault directory at `Vaults/obsidian-settings`, and its `.obsidian` files and directories are copied to all the other vaults.  (Pro tip: consider making a vault with a simple name like `obsidian-settings` for the sole purpose of setting up your Obsidian configuration.)

The default operation is to rename existing files so they have a date string appended, as a simple backup, to avoid data loss.  For example, the file `config` would be renamed to something like `config-2021-05-23T23:57:24.141428Z`.  Other files in the `.obsidian` directory are not affected.

If you prefer, you can have the utility nuke the whole `.obsidian` directory, and then create a new empty directory, to copy files into.  This reduces the clutter of the backups, at the expense of losing everything in the directory (including, for instance, `workspace` settings).  Obsidian is good about recreating files it needs in the directory, but please use `--rm` only if you understand the implications. In particular, consider making a separate backup of important `config` files from customized vaults.

The files and directories currently copied (as long as they exist in the source vault):

- `config` - general settings and plugin settings
- `starred.json` - which notes have been starred
- `plugins` - source code and settings for community plugins
- `snippets` - CSS snippets for customizing Obsidian's appearance
- `README.md` - optional file used for vaults distributed to others via Git

### Execute Command

To execute a command within each vault, use `-x` or `--execute`:

```shell
./osm.py -x 'git status'
```

For each vault, a line like this is printed:

```
# My Vault
```

Any output from the command is printed after that line.

### List ISO 8601-formatted .obsidian Backup Files

The `--update` command leaves backup files in the `.obsidian` directory with an ISO 8601-style date appended.  For example, this is a backup `config` file: `config-2021-05-23T23:57:24.141428Z`.

To list all of these files, use `--backup-list`:

```shell
./osm.py --backup-list
```

### Remove ISO 8601-formatted .obsidian Backup Files

The `--update` command leaves backup files in the `.obsidian` directory with an ISO 8601-style date appended.  For example, this is a backup `config` file: `config-2021-05-23T23:57:24.141428Z`.

To remove all of these files, use `--backup-remove`:

```shell
./osm.py --backup-remove
```

There is no undo for this operation. Consider using `--backup-list` before `--backup-remove` to double check that the files found are okay to remove.

## Possible Enhancements

Bug reports, enhancement suggestions, and pull requests are welcome at the [Obsidian Settings Manager repo](https://github.com/peterkaminski/obsidian-settings-manager).

Here are some possible enhancements already contemplated.

- List details of vault plugins, snippets, config.
- More fine-grained control over which files and directories are copied, and which destination vaults they are copied to.
  - Use `--input` / `-i` to specify a file that contains vault paths, instead of reading the vault paths from Obsidian.
  - Use `--config` / `-c` to specify a YAML file which specifies which files and directories to copy.
- Option to merge config files, rather than replace.
- More optional verbosity about what the utility is doing and not doing.
- Back up vaults to another location.
- Back up vault configuration to another location.
- Output commands to run on the OS's CLI, rather than actually executing actions.

## MIT License

Copyright (c) 2021 Peter Kaminski

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
