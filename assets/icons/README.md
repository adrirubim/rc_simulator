## Icon assets

### Source of truth

- Canonical vector icon is now packaged at `src/rc_simulator/resources/icons/rc-simulator.svg`.

### Windows

- `rc-simulator.ico`: icon for Windows shortcuts (`.lnk`). Windows Explorer does not support SVG icons for shortcuts.
  - If present, it should live next to the packaged SVG: `src/rc_simulator/resources/icons/rc-simulator.ico`.

### PNG exports

Generated from the canonical SVG (useful for docs, packaging, stores, etc.):

- `png/rc-simulator-16.png`
- `png/rc-simulator-24.png`
- `png/rc-simulator-32.png`
- `png/rc-simulator-48.png`
- `png/rc-simulator-64.png`
- `png/rc-simulator-128.png`
- `png/rc-simulator-256.png`
- `png/rc-simulator-512.png`

