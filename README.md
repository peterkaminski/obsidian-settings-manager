# Obsidian Settings Manager v0.3.2

## WARNING AND DISCLAIMER

WARNING: This utility manipulates files in all vaults that Obsidian knows about. It is written to only fiddle with the files in .obsidian (and with the `--exact-copy-of` flag, to delete the `.obsidian` directory and recreate it), and it is intended to be safe to use. HOWEVER, it is possible that unintentional data loss may occur, and so you should only use this utility if you have backups of all your files, and only if you understand the risks associated with using this utility.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

See LICENSE file for copyright license.

## Overview

This utility helps you manage [Obsidian](https://obsidian.md) settings (including plugins and snippets) across multiple vaults.

In the current incarnation, it can:

- List the vaults Obsidian knows about.
- Copy the settings, plugins, and snippets from one vault to all the other vaults.
  - By default, backups are made, but a flag can be used to reset the configuration and make the destination vaults' configs an exact copy.
- Dry-run option to see what commands would do, without doing it.
- Show a diff of what would change if a copy were done.
- Execute a command within each vault.
- List or remove backup files (created by the copy operation) from the `.obsidian` directory of all vaults.

Current notes and limitations:

- Early release, no significant testing yet.
- No options for specifying particular destination directories to copy to or to ignore.  In future versions, there may be more options providing more fine-grained control.
- No options for changing which files and directories are copied and which are ignored.  In future versions, there may be more options providing more fine-grained control.
- No option for selecting just a subset of your vaults to be affected by the Copy operation.
- Mac and Linux only (although Windows might not be too hard).
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

### Dry Run

For any command, show what would be done, without doing it. Add `-n` or `--dry-run` (in this example, to the `--backup-remove` command):

```shell
./osm.py -n --backup-remove
```

### Update Vault Configuration

To copy this files and directories from one Obsidian's `.obsidian` directory to all the other vaults, use `-u` or `--update`, with the directory name of the source vault after the flag:

```shell
./osm.py --update Vaults/obsidian-settings
```

In this example, there is an Obsidian vault directory at `Vaults/obsidian-settings`, and its `.obsidian` files and directories are copied to all the other vaults.  (Pro tip: consider making a vault with a simple name like `obsidian-settings` for the sole purpose of setting up your Obsidian configuration.)

The default operation is to rename existing files so they have a date string appended, as a simple backup, to avoid data loss.  For example, the file `config` would be renamed to something like `config-2021-05-23T23:57:24.141428Z`.  Other files in the `.obsidian` directory are not affected.

If you prefer, you can have the utility nuke the whole `.obsidian` directory, and then create a new empty directory, to copy files into.  This reduces the clutter of the backups, at the expense of losing everything in the directory (including, for instance, `workspace` settings).  Obsidian is good about recreating files it needs in the directory, but please use `--exact-copy-of` only if you understand the implications. In particular, consider making a separate backup of important `config` files from customized vaults. Also, do not use this option while Obsidian is running!

The files and directories currently copied (as long as they exist in the source vault):

- `config` - general settings and plugin settings
- `starred.json` - which notes have been starred
- `plugins` - source code and settings for community plugins
- `snippets` - CSS snippets for customizing Obsidian's appearance
- `README.md` - optional file used for vaults distributed to others via Git

See the `ITEMS_TO_COPY` global in the code to configure this.

### Diff-To

Like update but instead of copying, just show a diff against DIFF_TO instead. No changes are made. Use `-d` or `--diff-to`, with the directory name of the source vault after the flag:

```shell
./osm.py --diff-to Vaults/obsidian-settings
```

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

### Where Are My Vaults?

Normally OSM will find your vaults automatically by looking in the default Obsidian configuration directory for a file called `obsidian.json`, which is used by Obsidian to store the list of all the vaults it knows about.

The default locations for the Obsidian configuration directory:

- Mac, `/Users/<username>/Library/Application Support/obsidian`
- Linux, `/home/<username>/.config/obsidian`
- Windows, `C:\Users\<username>\AppData\obsidian`

If the `--list` option doesn't show your vaults or if you want OSM to use an alternate Obsidian configuration, use the `--root` option:

```shell
./osm.py --root /my/obsidian/root/directory [other commands as needed]
```

If you need to use this often, you can set the environment variable `OBSIDIAN_ROOT`,
so that you don't have to remember to use the `--root` option all the time:

```shell
export OBSIDIAN_ROOT=/my/obsidian/root/directory
```

For convenience, you can add the `export` command to your shell's initialization file (for example, `~/.zshrc` or `~/.bashrc`). Consult your shell documentation for more information about its initialization file.

If the `--root` option is used on the command line, its value is used; otherwise the environment variable is used; and if neither is set, the built-in OSM default is used.

## Possible Enhancements

Bug reports, enhancement suggestions, and pull requests are welcome at the [Obsidian Settings Manager repo](https://github.com/peterkaminski/obsidian-settings-manager).

Here are some possible enhancements already contemplated.

- List details of vault plugins, snippets, config.
    - workaround for community plugins: `./osm.py -x 'cat .obsidian/community-plugins.json'`
- More fine-grained control over which files and directories are copied, and which destination vaults they are copied to. This would replace the `ITEMS_TO_COPY` global.
  - Use `--input` / `-i` to specify a file that contains vault paths, instead of reading the vault paths from Obsidian.
  - Use `--config` / `-c` to specify a YAML file which specifies which files and directories to copy.
- Option to merge config files, rather than replace.
- Back up vaults to another location.
- Back up vault configuration to another location.
- `--backup-create` - just back up files without doing `--update`
- `--backup-restore ISO_8601_DATE` - restore from backup files
- Output commands to run on the OS's CLI, rather than actually executing or dry-running actions.
- Alpha-sort the vaults in `obsidian.json` (by changing `ts`)

## Contributors

Obsidian Settings Manager is open source. Pull requests and suggestions are gratefully received. Thank you to the following contributors!

- Peter Kaminski, [github/@peterkaminski](https://github.com/peterkaminski/)
- Doug Philips, [github/@dgou](https://github.com/dgou)

## MIT License

Copyright (c) 2021-2024 Peter Kaminski

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
