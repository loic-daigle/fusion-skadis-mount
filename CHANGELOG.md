# Changelog

## Unreleased
- **Horizontal boards:** the support pegs are now 14.75 x 4.75 mm (were 14 x 4, the same as the hook shaft)
  so they hold better in the board. The hooks keep their 14 x 4 mm shaft. Set with `PEG_S` / `PEG_T`.

## 1.1.0
- **Vertical-slot boards** (the normal way SKÅDIS is used) are now supported with the classic **L-shaped
  hook**: an obround tab through the slot and an obround lip turning down behind the board. The tab, lip and
  support pegs have fully rounded ends (end radius 2.5 mm, limited to half the width, so R2 with the 4 mm width).
  Choose the board type in the dialog ("Board slots"). Horizontal boards keep the rounded hook with the chamfered lip.
- Hook placement (one row along the top edge, 40 mm apart) and the support pegs work the same way for both.
- **Vertical boards are implemented but not tested yet.**

## 1.0.0
First release.

- **Add Skadis** command (Solid > Create): pick a planar face and its top edge. Made for boards with horizontal slots (vertical slots are not supported yet).
- Hooks in one row along the top edge, always 40 mm centre to centre, automatic or manual quantity.
- Support pegs in the other slot positions of the board (automatic or manual quantity).
- Built from ordinary Fusion features (sketch, extrude, sketch, extrude, chamfer) collected in one
  collapsed timeline group, so every step stays editable the normal way.
- Shaft length, lip thickness and chamfer size are user parameters.
- Live preview, and a debug log (`skadis_debug.log`) next to the add-in.
