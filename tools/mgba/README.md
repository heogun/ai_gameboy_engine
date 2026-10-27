# mGBA debugger

This project includes the official universal macOS mGBA 0.10.5 application bundle.
Its executable is `mGBA.app/Contents/MacOS/mGBA`; the upstream license is in `LICENSE`.

The emulator supports command-line launch and debugging:

- Normal launch: `mGBA.app/Contents/MacOS/mGBA path/to/game.gbc`
- Interactive command-line debugger: add `--debug`
- GDB remote debugging for IDEs and automation: add `--gdb` (listens on TCP port 2345)

Upstream release: https://github.com/mgba-emu/mgba/releases/tag/0.10.5
