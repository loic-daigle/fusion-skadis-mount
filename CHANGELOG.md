# Changelog

## 1.0.0
First release.

- **Add Skadis** command (Solid > Create): pick a planar face and its top edge. Made for boards with horizontal slots (vertical slots are not supported yet).
- Hooks in one row along the top edge, always 40 mm centre to centre, automatic or manual quantity.
- Support pegs in the other slot positions of the board (automatic or manual quantity).
- Built from ordinary Fusion features (sketch, extrude, sketch, extrude, chamfer) collected in one
  collapsed timeline group, so every step stays editable the normal way.
- Shaft length, lip thickness and chamfer size are user parameters.
- Live preview, and a debug log (`skadis_debug.log`) next to the add-in.
