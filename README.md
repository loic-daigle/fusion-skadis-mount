# SkadisMount - Fusion add-in for SKÅDIS pegboard hooks

A small [Autodesk Fusion](https://www.autodesk.com/products/fusion-360) add-in that turns any flat
face of your model into something you can hang on an **IKEA SKÅDIS** pegboard: you pick the face and
its top edge, and it adds rounded hook tabs and support pegs that fit the board's slots.

Everything is built from **normal Fusion features** (sketches, extrusions, a chamfer), so you can edit
the result the usual way afterwards.

> **Currently for horizontal-slot boards only.** The hooks are laid out for a SKÅDIS board whose slots run
> left/right (a board mounted turned by 90 degrees). Vertical-slot boards are not supported yet.

> Not affiliated with, endorsed by or sponsored by IKEA. SKÅDIS is a trademark of Inter IKEA Systems B.V.

## What it does

1. Click **Add Skadis** (Solid tab > Create).
2. Pick the **face** that will sit flat against the board.
3. Pick the **top edge** of that face (the border that is the top when the part hangs).
4. Click OK. A live preview is shown while you change the options.

### Placement rules

- **Hooks:** one single row along the top edge, always **40 mm centre to centre**, close to the top
  edge. The quantity is automatic (as many as fit) or set by hand. The lip of every hook overhangs
  towards the top edge.
- **Support pegs:** plain shafts (no lip) in the board's other slot positions, to make the part sit
  solidly. Rows are 20 mm apart and every other row is shifted by 20 mm, like the real board.
  Automatic mode fills every position that fits on the face, or you type how many you want (they are
  placed row by row, starting next to the hooks).

### Dialog options

| Option | Meaning |
| --- | --- |
| Face | Planar face that sits flat on the board |
| Top edge | Straight edge of that face that is the top |
| Automatic quantity / Number of hooks | Fill the edge with as many hooks as fit, or a fixed number |
| Support pegs / Automatic peg quantity / Number of support pegs | Add the pegs, fill the face, or a fixed number |
| Distance from top edge | Gap between the top edge and the top side of the hook shaft (default 1.5 mm) |
| Shaft length (board thickness) | Length of the shafts, default 5 mm |

## The hook

All sizes in millimetres (change them in the constants at the top of `SkadisMount.py`).

| Part | Size |
| --- | --- |
| Shaft | 14 x 4, fully rounded ends (R2), 5 long (the board thickness) |
| Lip | 10 x 7.5, 3 thick, on top of the shaft. Its 10 mm edge lies on one long side of the shaft, so it overhangs the shaft by 3.5 towards the top edge |
| Chamfer | 3 x 3 on the top edge of the lip's flush side (the side opposite the overhang) |

**Please check the board dimensions used** against your own SKÅDIS boards before printing: slots are
assumed to be 15 x 5 and run **horizontally** (the hook shaft, 14 x 4, lies along the slot), 5 mm board
thickness, hooks 40 mm apart in a row and rows 20 mm apart. The values are constants at the top of the
script.

## Editing the result

The add-in creates one collapsed timeline group named like **"Skadis: 3 hooks + 5 pegs"**. Expand it and
double-click any item as usual:

| Timeline item | What you can change |
| --- | --- |
| Skadis - shaft sketch | Move, delete or copy the shaft outlines (hooks and pegs) |
| Skadis - shafts | The extrusion of the shafts |
| Skadis - lip sketch | The lip rectangles |
| Skadis - lips | The extrusion of the lips |
| Skadis - lip chamfer | The chamfer |

`SkadisBoardThickness`, `SkadisLipHeight` and `SkadisChamfer` are also user parameters
(Modify > Change Parameters). To change the number of hooks or pegs, edit the sketches, or delete the
group and run **Add Skadis** again.

## Requirements

- Autodesk Fusion (Windows or macOS)
- A SKÅDIS board with **horizontal slots** (slots running left/right)
- A design with **Capture Design History** on (parametric). The hooks need the timeline.
- The face must belong to a body in the active component.

## Installation

1. Download the latest `SkadisMount-x.y.z.zip` from the [Releases](../../releases) page, or clone this
   repository, and unzip so that you have a folder named **`SkadisMount`** that contains
   `SkadisMount.py`, `SkadisMount.manifest` and a `resources` folder.
2. Put that folder in Fusion's add-ins folder:
   - Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`
   - macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`

   (Or in Fusion press `Shift+S`, open the **Add-Ins** tab, click the green **+** and pick the folder.)
3. In Fusion press `Shift+S`, open the **Add-Ins** tab, select **SkadisMount** and click **Run**.
   Tick *Run on Startup* if you want it loaded every time.
4. The **Add Skadis** button appears in the Solid tab, Create panel.

After changing or replacing the add-in files, stop and run it again.

## Troubleshooting

- **No button:** the folder must be called `SkadisMount` and contain the `.py` and `.manifest` files
  directly (not one folder deeper). Make sure the add-in is running (Shift+S > Add-Ins).
- **"Please turn on Capture Design History":** right-click the top node in the browser and enable it.
- **"No hook fits along this edge":** the face is too small for a 14 x 4 mm shaft at the current
  distance from the edge. Use a smaller distance or a bigger face.
- **Something failed:** an error message with details is shown, and the add-in undoes what it had
  already built. There is also a log next to the add-in, `skadis_debug.log`. Please include both in a
  bug report.

## Design notes

The first versions wrapped everything in a single Fusion *custom feature* node, so the whole hook
would edit from one dialog. In testing, Fusion never offered *Edit Feature* for custom features created
by an add-in (the custom feature API is still marked as a preview by Autodesk), so version 1.0 uses
ordinary features grouped in the timeline instead.

## License

[MIT](LICENSE)
