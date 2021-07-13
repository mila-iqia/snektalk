
**Note:** This project is at a very early stage and no aspect of it should be considered stable before v0.1.0 is released.

# S N E K T A L K

Snektalk is a groundbreaking new kind of REPL.

* Live code editing
* Rich and interactive object representations
* Built-in debugger
* Inspect a program's internal state
* Connect to remote processes

# Install

```bash
pip install snektalk
```

# Usage

You can simply use `snektalk` instead of `python` to run a script.

```
usage: snektalk [-h] [--connect VALUE] [-m VALUE] [--no-watch] [--port NUM]
                [--socket VALUE] [--thread] [--version]
                [SCRIPT] ...

positional arguments:
  SCRIPT                Path to the script to run
  ARGV                  Script arguments

optional arguments:
  -h, --help            show this help message and exit
  --connect VALUE, -c VALUE
                        Hostname to connect to an existing instance
  -m VALUE              Module or module:function to run
  --no-watch            Don't watch changes on the filesystem
  --port NUM, -p NUM    Server port
  --socket VALUE, -S VALUE
                        Path to socket
  --thread, -t          Run the program in a thread
  --version             Show the version
```

# Features

At a glance Snektalk might appear similar to Jupyter notebooks, but it follows different paradigms. It has no "cells" and is meant to be used like a straightforward REPL or command line. At the same time, it has many features neither standard REPLs nor Jupyter tend to have.

## Edit functions and data

Simply type `/edit func` and you will be greeted with a small inline editor for the source code of `func`. You may change it and hit `Ctrl+Enter` to change it in the current process, or `Ctrl+Shift+Enter` to save it back into the original file it came from. You can come back to it at any time, of course.

![edit](https://user-images.githubusercontent.com/599820/116953136-7c74de00-ac5a-11eb-9868-a53da72a1f5d.gif)

Virtually *any* function can be edited, whether it is yours or comes from a third party library or even the standard library.

`/edit` also works on data structures. You will be given an editable sandbox where you can change dictionaries, reorder lists, change the values of the fields of an object, and so on. Objects can even define a custom `__snek_edit__` method to control how they are edited.

![edit-data](https://user-images.githubusercontent.com/599820/116953144-826abf00-ac5a-11eb-93b7-cfdcc46ac166.gif)

## Rich and interactive representations

Snektalk does not print lists, dictionaries or objects as mere text, but as rich HTML objects using [hrepr](https://github.com/breuleux/hrepr).

![repr](https://user-images.githubusercontent.com/599820/116953095-5ea77900-ac5a-11eb-8091-5b27a3a795dc.gif)

`Ctrl+Click` (or `Cmd+Click` on Mac) the representation of an object to put it in a temporary variable. This makes it very easy to test or play with objects that are deeply nested in another.

![click](https://user-images.githubusercontent.com/599820/116953201-ac23e600-ac5a-11eb-9464-3aeccc9632d0.gif)

Representations are highly customizable and recursive representations can be defined and configured in a snap. See [here](https://github.com/breuleux/hrepr#custom-representations) for how to define custom representations.

The representation of exceptions is particularly interesting because each frame is associated to a live editor, so you can simply fix the error right there as you see it.

![exc](https://user-images.githubusercontent.com/599820/116953211-b34af400-ac5a-11eb-9d7e-37b51a7e955f.gif)

## Visualization

Snektalk supports elaborate visualizations: plots, graphs, and so on. Integrating a new or existing JavaScript library is mostly a matter of linking it from a CDN and writing a small wrapper.

![plot](https://user-images.githubusercontent.com/599820/116953224-ba720200-ac5a-11eb-8a4e-aba17fb214bc.gif)

It is also easy to configure visualizations so that various interactions call Python callbacks. One great use of this feature is the ability to click on nodes or points in a graph to put the underlying data in a variable and paste it into the REPL's input box so that you can analyze it further.

![graph](https://user-images.githubusercontent.com/599820/116955206-e2b02f80-ac5f-11eb-8474-dbdcd59cdd3a.gif)

## Debugging

`/debug f(x, y)` will enter a function call in debugger mode. Snektalk's debugger is quite similar to `pdb` and the usual `pdb` commands (`step`, `next`, `continue`, etc.) should work just the same.

![debug](https://user-images.githubusercontent.com/599820/116955224-eba10100-ac5f-11eb-81a8-4b042718611b.gif)

## Threads

`/thread f(x, y)` will run `f(x, y)` in a separate thread, which lets you keep working while it's running. Each thread is given a mnemonic name so that you can easily `/kill` them.

![thread](https://user-images.githubusercontent.com/599820/116955232-f0fe4b80-ac5f-11eb-8578-079f5e753052.gif)

You may use `snektalk -t` to start the main script in a thread, giving you immediate access to the REPL. This will allow you to inspect or fiddle with the global state while the script is running, among other things.

## Probing

Through [ptera](https://github.com/breuleux/ptera), Snektalk provides easy ways to probe variables anywhere inside your program.

![accumulate](https://user-images.githubusercontent.com/599820/125383483-793a5480-e365-11eb-9f79-343d4f0cfe53.gif)

# Using on a remote

You can run `snektalk` on a remote computer and connect to it over SSH. To do so, you will need to run two commands:

**On remote side:**

Run `snektalk` on the remote side with the `-S` option to connect to a UNIX socket on the filesystem. The interface will be served through that socket instead of a port.

```bash
user@remote$ snektalk -S ~/sock/script.sock script.py
```

**On local computer:**

Once the remote process is running, run `snektalk` with the `-c` option to specify which host to connect to, and `-S` pointing to the socket file.

```bash
me@local$ snektalk -c user@remote -S sock/script.sock
```

This will work for the whole duration of the remote process (note that the local Snektalk invocation doesn't do much more than invoke the right SSH command to forward the remote socket to a local port).

**Note about compute nodes:** In order to facilitate use on clusters where the compute nodes may only be available through a connection to the login node, Snektalk will store the hostname in a separate file (`sock/script.host` in the above example) and will attempt to connect to it automatically. Therefore, you should be able to run `snektalk` on a compute node, then give the login node as the argument to `-c`, and Snektalk will use the login node as a jump host to connect to the right compute node.

# Commands

* `/debug expr` -- Debug an expression
* `/dir expr` -- List all members of the object returned by the expression
  * `?expr` -- Same as `/dir expr`
* `/edit expr` -- Open an editor for the object returned by the expression
* `/quit` -- Quit Snektalk
* `/restart` -- Restart Snektalk with the same initial command
* `/shell command` -- Run shell command
  * `//command` -- Same as `/shell command`
* `/status` -- List all the status messages received so far

## Thread-related commands

* `/attach thread` -- Switch to the REPL of the named thread (you can also click on the prompt to list the threads, then click on the one you want to attach)
* `/detach` -- Undo last /attach
* `/kill thread` -- Stop a named thread
* `/thread expr` -- Run expression in new thread

# Keyboard and mouse bindings

Note: in what follows, `Cmd+X` means `Cmd+X` on MacOS and `Ctrl+X` on other platforms, unless otherwise specified.

## Global bindings

* `Cmd+P` -- Focus the REPL
* `Cmd+Click` -- Put object in a variable
* `Cmd+Alt+Click` -- Pin to the side

## Repl

* `Shift+Enter` -- Add new line in REPL without submitting
* `Ctrl+Enter` -- Submit
* `Up/Down` -- Go up/down in history (filtered by contents of REPL)
* `Ctrl+R` -- Open history popup (fuzzy search)
  * Note: `Shift-Up/Down` when history popup is active will select multiple entries
* `Ctrl+L` -- Clear all scrollback
* `Ctrl+C` (MacOS) -- Interrupt current command
* `Cmd+K Cmd+K` -- Interrupt current command (that's `Cmd+K`, twice)
* `Cmd+B`, `Cmd+Shift+B` -- Cycle through visible editors and REPL

## Function editor

* `Ctrl+Enter` -- Make live and focus REPL
* `Ctrl+Shift+Enter` -- Make live, commit to file, and focus REPL
* `Cmd+S` -- Make live
* `Cmd+Shift+S` -- Make live and commit to file
* `Cmd+B`, `Cmd+Shift+B` -- Cycle through visible editors and REPL

# Misc

* The status bar at the bottom can be clicked to view a list of all events
* Click the prompt to reveal a thread selector; if you put a breakpoint in a function called by a different thread, you need to switch to that thread to interact with the breakpoint.
