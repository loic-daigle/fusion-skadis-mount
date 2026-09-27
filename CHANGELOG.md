# Changelog

## 1.2.1
- **Horizontal boards:** the support pegs are now 14.75 x 4.75 mm (were 14 x 4, the same as the hook shaft)
  so they hold better in the board. The hooks keep their 14 x 4 mm shaft. Set with `PEG_S` / `PEG_T`.
- Fixed "invalid argument parameter" when measuring the face for the support pegs: an edge that refuses a
  point no longer stops the command (edge ends and the face's bounding box are used as backup).
- The log (`skadis_debug.log`) now records the real version and the file path when the add-in starts, and
  error messages show the version, so it is easy to see which copy Fusion is running.

## 1.2.0
- New **Hook spacing** option: *Every 40 mm* (as before) or *Spread to the ends*. Spread puts the hooks in the
  outermost slots that fit, with gaps of 40, 80, ... mm, and never forces a hook into the centre: with automatic
  quantity an odd row drops its centre hook (for example a 100 mm wide part gets 2 hooks 80 mm apart instead of
  3 hooks 40 mm apart). With a set number of hooks they are spread as evenly as the slots allow.
- *Spread to the ends* is the default for vertical boards (L hooks); horizontal boards keep *Every 40 mm*.
  Switching the board type switches this default, and you can still pick either.

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
