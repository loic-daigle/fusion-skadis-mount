# -*- coding: utf-8 -*-
"""
SkadisMount - Fusion 360 add-in  (v1.2.1)

Select a planar face, then the border of that face that is the TOP, choose the type of board
(horizontal or vertical slots) and click OK  (Solid > Create > Add Skadis).

Two hook types, one per board type:
  * Horizontal slots  -> rounded 14 x 4 mm shaft + 10 x 7.5 x 3 mm lip overhanging towards the
                         top edge, with a 3 x 3 mm chamfer on the opposite side
  * Vertical slots    -> (implemented but NOT TESTED yet) the classic L-shaped hook: an obround 4 x 5 mm tab through the slot and a
    (normal SKADIS)      4 mm wide obround lip turning 8 mm down behind the board (2.5 mm thick)
The sizes are constants at the top of this file.

Everything is built from ordinary Fusion features, collected in ONE collapsible timeline
group called "Skadis (horizontal|vertical): N hooks + M pegs". Expand the group and double-click
any item to edit it exactly like a normal Fusion feature:

  Sketch  "Skadis - shaft sketch"   outlines of every hook tab and support peg
                                     -> edit it to move / delete / copy shafts
  Extrude "Skadis - shafts"          the shafts, length = parameter SkadisBoardThickness
  Sketch  "Skadis - lip sketch"      lip rectangles on top of the hook shafts
  Extrude "Skadis - lips"            parameter SkadisLipHeight
  Chamfer "Skadis - lip chamfer"     horizontal boards only, parameter SkadisChamfer

Placement rules (both board types)
  * hooks: one row along the top edge, close to the top edge; quantity automatic or set by hand.
    Hook spacing "every 40 mm" packs them 40 mm centre to centre (an odd count has one in the
    centre); "spread to the ends" (default for L hooks) uses the outermost slots that fit with
    gaps of 40, 80, ... mm, and the automatic quantity then skips the centre hook (3 -> 2, 5 -> 4)
  * support pegs (the hook tab without the lip) fill the other slot positions of the board:
    rows 20 mm apart, alternate rows shifted 20 mm sideways; automatic = every peg that fits,
    otherwise you type how many (row by row, starting next to the hooks)
Needs a design with "Capture Design History" on (parametric).
"""
import math
import os
import traceback

import adsk.core
import adsk.fusion

# ----------------------------------------------------------------------------
# SKADIS board (mm) -- verify against your board!
# ----------------------------------------------------------------------------
HOOK_PITCH = 40.0     # distance between neighbouring slots in a row (hook gaps are multiples of it)
DEF_BOARD_T = 5.0     # board thickness = shaft length (editable)
DEF_MARGIN = 1.5      # gap between the top edge and the shaft's top side (editable)
PEG_ROW_GAP = 20.0    # slot rows are 20 mm apart (alternate rows shifted 20 mm sideways)

# ----------------------------------------------------------------------------
# Hook design (mm)
# ----------------------------------------------------------------------------
SHAFT_S = 14.0        # shaft length (along the slot)
SHAFT_T = 4.0         # shaft width (across the slot); the ends are full round (R = SHAFT_T / 2)
CORNER_R = SHAFT_T / 2.0   # the shaft ends are full round
LIP_S = 10.0          # lip size along the slot
LIP_W = 7.5           # lip size across the slot (overhangs the shaft by LIP_W - SHAFT_T)
LIP_H = 3.0           # lip thickness
CHAMFER = 3.0         # chamfer on the top edge of the flush 10 mm side (opposite the overhang)

# Vertical-slot boards (the normal way SKADIS is used) get the classic L-shaped hook: a tab that goes
# through the slot, then turns downwards behind the board. Seen from the side it is an "L".
V_SHAFT_W = 4.0       # tab width across the slot (along the row)
V_SHAFT_H = 5.0       # tab height along the slot (up/down)
V_LIP_LEN = 8.0       # how far the lip reaches down below the tab, behind the board
V_LIP_H = 2.5         # lip thickness behind the board
V_RADIUS = 2.5        # end radius of tab, lip and pegs (obround). It can never exceed half the width,
                      # so with the 4 mm width it becomes 2.0; a 5 mm wide part gets the full 2.5

MM = 0.1              # Fusion's internal unit is cm

VERSION = '1.2.1'     # keep in step with SkadisMount.manifest

CMD_ID = 'skadisMountCmd'
OLD_IDS = ('skadisMountEditBtn', 'skadisMountEditCmd')   # leftovers of the earlier experimental custom-feature builds
PANEL_ID = 'SolidCreatePanel'
WORKSPACE_ID = 'FusionSolidEnvironment'

_app = None
_ui = None
_handlers = []
_registered = []         # (event, handler) pairs to detach again in stop()


def _log(msg):
    """Tiny debug log next to the add-in (skadis_debug.log)."""
    try:
        import datetime
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'skadis_debug.log')
        with open(path, 'a') as f:
            f.write('{}  {}\n'.format(datetime.datetime.now().strftime('%H:%M:%S'), msg))
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Small vector helpers (plain tuples, no Fusion objects)
# ----------------------------------------------------------------------------
def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def add(*vs):
    return tuple(sum(v[i] for v in vs) for i in range(3))


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def unit(a):
    length = math.sqrt(dot(a, a))
    return None if length < 1e-9 else mul(a, 1.0 / length)


def hook_offsets(count):
    """Positions (mm) of `count` hooks along the row: 40 mm apart, centred on 0."""
    return [(i - (count - 1) / 2.0) * HOOK_PITCH for i in range(count)]


def spread_offsets(slots, count):
    """
    `count` hooks picked from the `slots` slot positions of hook_offsets(slots), spread out:
    the two outer slots are always used, the others as evenly as possible, symmetric around 0,
    so the gaps are multiples of 40 mm. An even count never uses the centre slot.
    Returns None when no symmetric choice exists (an odd count needs an odd number of slots).
    """
    grid = hook_offsets(slots)
    if count >= slots:
        return grid
    if count % 2 and slots % 2 == 0:
        return None
    idx = set()
    for j in range(count // 2):                           # left half, mirrored to the right
        i = int(math.floor(j * (slots - 1) / (count - 1.0) + 0.5))
        idx.update((i, slots - 1 - i))
    if count % 2:
        idx.add((slots - 1) // 2)
    return [grid[i] for i in sorted(idx)] if len(idx) == count else None


def hook_layouts(upper, auto, requested, spread):
    """
    Hook rows to try, best first; plan_row keeps the first one that fits on the face.
      packed: `count` hooks 40 mm apart (an odd count always has one in the centre).
      spread: the hooks go to the outermost slots that fit, with gaps of 40, 80, ... mm.
              Automatic quantity drops the centre hook of an odd row (3 -> 2 at the ends,
              5 -> 4, ...); a single hook stays in the centre.
    """
    if not spread:
        for k in range(upper if auto else requested, 0, -1):
            yield hook_offsets(k)
        return
    if auto:
        for m in range(upper, 0, -1):
            yield spread_offsets(m, m if m % 2 == 0 or m == 1 else m - 1)
        return
    for k in range(requested, 0, -1):
        for m in range(max(upper, k), k - 1, -1):
            layout = spread_offsets(m, k)
            if layout is not None:
                yield layout


def frame_from_edge(on_face, n, a, b, centroid):
    """
    Frame built from the chosen top edge (a -> b, cm). Returns (mid, s, t, edge_len) or an
    error string.  mid = middle of the edge, s = row direction (slots run along it),
    t = in the face plane, pointing from the face towards the top edge.
    """
    e_dir = unit(sub(b, a))
    if e_dir is None:
        return 'The top border is too short.'
    edge_len = math.sqrt(dot(sub(b, a), sub(b, a)))
    mid = mul(add(a, b), 0.5)

    perp = unit(cross(n, e_dir))                          # in the face plane, across the edge
    delta = 0.05                                          # 0.5 mm
    if on_face(add(mid, mul(perp, -delta))):
        up = perp                                         # face lies on the -perp side
    elif on_face(add(mid, mul(perp, delta))):
        up = mul(perp, -1.0)
    else:
        up = perp if dot(sub(mid, centroid), perp) > 0 else mul(perp, -1.0)
    s = cross(n, up)
    return mid, s, up, edge_len


def _rrect_area(length, width, radius):
    """Area (mm2) of a rectangle with rounded corners; radius = width / 2 gives an obround."""
    r = min(radius, width / 2.0, length / 2.0)
    return length * width - (4.0 - math.pi) * r * r


def get_spec(vertical):
    """
    Shape data of the hooks for a board with vertical (True) or horizontal (False) slots.
    All in mm, in the frame  s = along the row / edge,  t = towards the top edge.
    """
    if vertical:
        hs, ht = V_SHAFT_W / 2.0, V_SHAFT_H / 2.0
        r = min(V_RADIUS, hs, ht)
        straight = ht - r                       # half length of the straight sides
        return dict(vertical=True, half_s=hs, half_t=ht,
                    outline=[(0, 0), (0, ht), (0, -ht), (hs, 0), (-hs, 0),
                             (hs, straight), (hs, -straight), (-hs, straight), (-hs, -straight)],
                    shaft_area=_rrect_area(V_SHAFT_H, V_SHAFT_W, r),
                    lip_area=_rrect_area(V_SHAFT_H + V_LIP_LEN, V_SHAFT_W, r),
                    lip_h=V_LIP_H, chamfer=False, label='vertical', hook_word='L hook')
    half_s, half_t = SHAFT_S / 2.0, SHAFT_T / 2.0
    core = half_s - CORNER_R
    return dict(vertical=False, half_s=half_s, half_t=half_t,
                outline=[(0, 0), (half_s, 0), (-half_s, 0), (core, half_t), (core, -half_t),
                         (-core, half_t), (-core, -half_t), (0, half_t), (0, -half_t)],
                shaft_area=(SHAFT_S - SHAFT_T) * SHAFT_T + math.pi * (SHAFT_T / 2.0) ** 2,
                lip_area=LIP_S * LIP_W,
                lip_h=LIP_H, chamfer=True, label='horizontal', hook_word='hook')


def plan_row(on_face, extents, frame, margin, auto, requested,
             pegs=True, peg_auto=True, peg_requested=0, spec=None, spread=False):
    """
    Pure placement logic (lengths in cm, offsets in mm).
    on_face(point) -> bool tells whether a point of the face plane lies on the face.
    extents(origin, s, t) -> (smin, smax, tmin, tmax) of the face in cm, or None.
    Returns (hooks_mm, peg_list, peg_fit) or an error string.
      peg_list = [(offset_mm, row), ...]  row 0 = hook row, row 1 = 20 mm lower, ...
      peg_fit  = how many pegs would fit in total.
    spread=False: hooks 40 mm apart; True: hooks spread to the ends (see hook_layouts).
    """
    spec = spec or get_spec(False)
    mid, s, t, edge_len = frame
    half_s, half_t = spec['half_s'], spec['half_t']
    t_base = -(margin + half_t * MM)                      # hook centre line, below the edge

    # points of the shaft outline (mm) - all must lie on the face
    outline = spec['outline']

    def fits_at(off, tb):
        base = add(mid, mul(s, off * MM), mul(t, tb))
        for x, y in outline:
            if not on_face(add(base, mul(s, x * MM), mul(t, y * MM))):
                return False
        return True

    hook_fit = {}                                         # offset -> fits in the hook row

    def fits(layout):
        for off in layout:
            key = round(off, 6)
            if key not in hook_fit:
                hook_fit[key] = fits_at(off, t_base)
            if not hook_fit[key]:
                return False
        return True

    upper = int(edge_len / (HOOK_PITCH * MM)) + 2
    for hooks in hook_layouts(upper, auto, requested, spread):
        if not fits(hooks):
            continue
        peg_list, peg_fit = [], 0
        ext = extents(mid, s, t) if pegs else None
        if ext is not None:
            cands = []                                    # (offset_mm, row)
            smin, smax, tmin, _ = ext
            row_step = PEG_ROW_GAP * MM
            for row in range(0, int(max(0.0, -tmin) / row_step) + 2):
                tb = t_base - row * row_step
                if tb - half_t * MM < tmin - 1e-6:
                    break                                 # would poke out below the face
                start = hooks[0] + (row % 2) * PEG_ROW_GAP
                j_lo = int(math.floor((smin / MM - 2 * half_s - start) / HOOK_PITCH))
                j_hi = int(math.ceil((smax / MM + 2 * half_s - start) / HOOK_PITCH))
                for j in range(j_lo, j_hi + 1):
                    off = start + j * HOOK_PITCH
                    if row == 0 and any(abs(off - h) < 1e-6 for h in hooks):
                        continue                          # that slot already holds a hook
                    if fits_at(off, tb):
                        cands.append((off, row))
            # row by row starting next to the hooks (the hook row's leftovers last),
            # and from the middle outwards inside a row
            cands.sort(key=lambda c: (c[1] == 0, c[1], abs(c[0]), c[0]))
            peg_fit = len(cands)
            peg_list = cands if peg_auto else cands[:peg_requested]
        return hooks, peg_list, peg_fit
    return ('No hook fits along this edge. The shaft is {:g} x {:g} mm and must sit fully on '
            'the face, {:.1f} mm below the top edge. Try a smaller distance from the '
            'edge or a bigger face.'.format(2 * half_s, 2 * half_t, margin / MM))


# ----------------------------------------------------------------------------
# Fusion helpers
# ----------------------------------------------------------------------------
def _p3(v):
    return adsk.core.Point3D.create(v[0], v[1], v[2])


def _face_extents(face, origin, s, t):
    """Bounding box of the face in the (s, t) frame -> (smin, smax, tmin, tmax) in cm."""
    ss, ts = [], []

    def add_point(p):
        d = sub((p.x, p.y, p.z), origin)
        ss.append(dot(d, s))
        ts.append(dot(d, t))

    for edge in face.edges:
        for v in (edge.startVertex, edge.endVertex):
            if v is not None:
                add_point(v.geometry)
        try:
            ev = edge.evaluator
            ok, lo, hi = ev.getParameterExtents()
        except Exception:
            continue
        if not ok:
            continue
        steps = 32
        for i in range(steps + 1):
            # Fusion refuses parameters even a rounding error outside [lo, hi]; skip those
            u = min(max(lo + (hi - lo) * i / steps, min(lo, hi)), max(lo, hi))
            try:
                ok, p = ev.getPointAtParameter(u)
            except Exception:
                continue
            if ok:
                add_point(p)
    if not ss:
        # last resort: the corners of the face's bounding box (bigger than the face, but every
        # peg is still checked against the real face before it is placed)
        bb = face.boundingBox
        lo_, hi_ = bb.minPoint, bb.maxPoint
        for x in (lo_.x, hi_.x):
            for y in (lo_.y, hi_.y):
                for z in (lo_.z, hi_.z):
                    add_point(adsk.core.Point3D.create(x, y, z))
    return min(ss), max(ss), min(ts), max(ts)


def _on_face(face, point):
    ev = face.evaluator
    ok, param = ev.getParameterAtPoint(_p3(point))
    return ok and ev.isParameterOnFace(param)


def a_pt(vertex):
    p = vertex.geometry
    return (p.x, p.y, p.z)


def frame_for(face, edge):
    """(n, frame) for a face + its top edge, or an error string."""
    ok, nrm = face.evaluator.getNormalAtPoint(face.pointOnFace)
    if not ok:
        return 'Could not read the face normal.'
    n = unit((nrm.x, nrm.y, nrm.z))
    c = face.centroid
    frame = frame_from_edge(lambda pt: _on_face(face, pt), n, a_pt(edge.startVertex),
                            a_pt(edge.endVertex), (c.x, c.y, c.z))
    if isinstance(frame, str):
        return frame
    return n, frame


def _check_selection(face, edge):
    if face is None:
        return 'Please select a planar face.'
    if edge is None:
        return 'Please select a straight edge as the top border.'
    if face.assemblyContext is not None:
        return ('Please activate the component that owns this body first '
                '(right-click it in the browser > Activate), then try again.')
    if edge.entityToken not in set(e.entityToken for e in face.edges):
        return 'The top border must be one of the selected face\'s own edges.'
    if edge.startVertex is None or edge.endVertex is None:
        return 'The top border must be a straight edge.'
    return None


# ----------------------------------------------------------------------------
# Building the native features
# ----------------------------------------------------------------------------
def _user_param(design, base_name, mm_value, comment, created):
    """A user parameter with a unique name (SkadisBoardThickness, SkadisBoardThickness_2, ...)."""
    params = design.userParameters
    name, i = base_name, 1
    while params.itemByName(name) is not None:
        i += 1
        name = '{}_{}'.format(base_name, i)
    p = params.add(name, adsk.core.ValueInput.createByString('{:.4f} mm'.format(mm_value)),
                   'mm', comment)
    created.append(p)
    return p


def _to_sketch(sketch, world):
    p = sketch.modelToSketchSpace(_p3(world))
    return adsk.core.Point3D.create(p.x, p.y, 0.0)      # sketch points must lie in the sketch plane


def _join(sketch, a, b):
    try:
        sketch.geometricConstraints.addCoincident(a, b)
    except Exception:
        pass


def _draw_stadium(sketch, base, s, t):
    """14 x 4 mm outline with R2 ends: two lines + two arcs, centred on `base`."""
    hc = (SHAFT_S / 2.0 - SHAFT_T / 2.0) * MM          # half length of the straight part
    hw = SHAFT_T / 2.0 * MM                            # half width = end radius

    def P(a, b):
        return _to_sketch(sketch, add(base, mul(s, a), mul(t, b)))

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs
    l1 = lines.addByTwoPoints(P(-hc, hw), P(hc, hw))
    a1 = arcs.addByThreePoints(P(hc, hw), P(hc + hw, 0.0), P(hc, -hw))
    l2 = lines.addByTwoPoints(P(hc, -hw), P(-hc, -hw))
    a2 = arcs.addByThreePoints(P(-hc, -hw), P(-hc - hw, 0.0), P(-hc, hw))
    _join(sketch, l1.endSketchPoint, a1.startSketchPoint)
    _join(sketch, a1.endSketchPoint, l2.startSketchPoint)
    _join(sketch, l2.endSketchPoint, a2.startSketchPoint)
    _join(sketch, a2.endSketchPoint, l1.startSketchPoint)


def _draw_rounded_rect(sketch, center, u, v, length, width, radius):
    """
    Rectangle `length` (along u) x `width` (along v) mm with corner radius `radius`, centred on
    `center`. When the radius reaches half the width the ends are full round: an obround.
    """
    hl, hw = length / 2.0, width / 2.0
    r = min(radius, hw, hl)
    k = math.sqrt(2.0) / 2.0

    def P(a, b):
        return _to_sketch(sketch, add(center, mul(u, a * MM), mul(v, b * MM)))

    def line(a0, b0, a1, b1):
        return ('line', (a0, b0), (a1, b1))

    def arc(cx, cy, d0, d1):
        m = ((d0[0] + d1[0]) * k, (d0[1] + d1[1]) * k)
        return ('arc', (cx + r * d0[0], cy + r * d0[1]), (cx + r * m[0], cy + r * m[1]),
                (cx + r * d1[0], cy + r * d1[1]))

    segs = [line(-hl + r, -hw, hl - r, -hw), arc(hl - r, -hw + r, (0, -1), (1, 0)),
            line(hl, -hw + r, hl, hw - r), arc(hl - r, hw - r, (1, 0), (0, 1)),
            line(hl - r, hw, -hl + r, hw), arc(-hl + r, hw - r, (0, 1), (-1, 0)),
            line(-hl, hw - r, -hl, -hw + r), arc(-hl + r, -hw + r, (-1, 0), (0, -1))]

    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs
    ents = []
    for seg in segs:
        if seg[0] == 'line':
            (a0, b0), (a1, b1) = seg[1], seg[2]
            if abs(a1 - a0) + abs(b1 - b0) < 1e-6:
                continue                                  # no straight part (obround end)
            ents.append(lines.addByTwoPoints(P(a0, b0), P(a1, b1)))
        else:
            ents.append(arcs.addByThreePoints(P(*seg[1]), P(*seg[2]), P(*seg[3])))
    for i, e in enumerate(ents):
        _join(sketch, e.endSketchPoint, ents[(i + 1) % len(ents)].startSketchPoint)


def _draw_rect(sketch, base, s, t, s0, s1, t0, t1):
    """Rectangle from (s0, t0) to (s1, t1), in mm relative to `base` (s = row, t = up)."""
    corners = [(s0, t0), (s1, t0), (s1, t1), (s0, t1)]
    pts = [_to_sketch(sketch, add(base, mul(s, a * MM), mul(t, b * MM))) for a, b in corners]
    lines = sketch.sketchCurves.sketchLines
    first = lines.addByTwoPoints(pts[0], pts[1])
    prev = first
    for k in (2, 3):
        prev = lines.addByTwoPoints(prev.endSketchPoint, pts[k])
    lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)


def _draw_shaft(sketch, base, s, t, spec):
    """The tab that goes through the slot: rounded 14 x 4 (horizontal) or obround 4 x 5 (L hook)."""
    if spec['vertical']:
        _draw_rounded_rect(sketch, base, t, s, V_SHAFT_H, V_SHAFT_W, V_RADIUS)
    else:
        _draw_stadium(sketch, base, s, t)


def _draw_lip(sketch, base_top, s, t, spec):
    """
    Horizontal boards: 10 x 7.5 mm, its 10 mm edge on the shaft's flush side, overhanging up.
    Vertical boards (L hook): obround, 4 mm wide, from the top of the tab down 8 mm below it.
    """
    if spec['vertical']:
        centre = add(base_top, mul(t, -V_LIP_LEN / 2.0 * MM))
        _draw_rounded_rect(sketch, centre, t, s, V_SHAFT_H + V_LIP_LEN, V_SHAFT_W, V_RADIUS)
    else:
        t0 = -SHAFT_T / 2.0
        _draw_rect(sketch, base_top, s, t, -LIP_S / 2.0, LIP_S / 2.0, t0, t0 + LIP_W)


def _all_profiles(sketch, expected, area_mm2):
    """The closed outlines we drew (recognised by their area), never the face region around them."""
    profs = adsk.core.ObjectCollection.create()
    for pr in sketch.profiles:
        try:
            a = pr.areaProperties().area * 100.0            # cm2 -> mm2
        except Exception:
            a = None
        if a is None or abs(a - area_mm2) <= 0.03 * area_mm2:
            profs.add(pr)
    if profs.count != expected:
        raise RuntimeError('{} closed outlines expected in "{}", found {}'.format(
            expected, sketch.name, profs.count))
    return profs


def _extrude(comp, sketch, profiles, expr, n):
    """Join-extrude `profiles` by `expr` (a parameter name) away from the body, along n."""
    ext_in = comp.features.extrudeFeatures.createInput(
        profiles, adsk.fusion.FeatureOperations.JoinFeatureOperation)
    _, _, _, z = sketch.transform.getAsCoordinateSystem()
    direction = (adsk.fusion.ExtentDirections.PositiveExtentDirection
                 if dot((z.x, z.y, z.z), n) > 0
                 else adsk.fusion.ExtentDirections.NegativeExtentDirection)
    ext_in.setOneSideExtent(
        adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString(expr)),
        direction)
    return comp.features.extrudeFeatures.add(ext_in)


def _rollback(design, count_before, params):
    """Undo a half-finished build: delete what was added to the timeline, then the parameters."""
    try:
        tl = design.timeline
        while tl.count > count_before:
            tl.item(tl.count - 1).entity.deleteMe()
    except Exception:
        pass
    for p in params:
        try:
            p.deleteMe()
        except Exception:
            pass


def create_features(design, face, edge, st, commit=True):
    """
    Builds sketch/extrude/sketch/extrude/chamfer on the face.
    st = dict(auto, count, pegs, peg_auto, peg_count, margin_cm, board_cm, vertical)
    commit=False (live preview): no timeline group.  Returns a message for the user or None.
    """
    err = _check_selection(face, edge)
    if err:
        return err
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        return ('Please turn on "Capture Design History" for this design '
                '(right-click the top node in the browser). The hooks are built from '
                'normal, editable Fusion features and need the timeline.')
    fr = frame_for(face, edge)
    if isinstance(fr, str):
        return fr
    n, frame = fr
    mid, s, t, _ = frame
    spec = get_spec(st.get('vertical', False))

    plan = plan_row(lambda pt: _on_face(face, pt),
                    lambda o, s_, t_: _face_extents(face, o, s_, t_),
                    frame, st['margin_cm'], st['auto'], st['count'],
                    st['pegs'], st['peg_auto'], st['peg_count'], spec,
                    st.get('spread', False))
    if isinstance(plan, str):
        return plan
    hooks, peg_list, peg_fit = plan

    board_t = st['board_cm']
    lip_h = spec['lip_h'] * MM
    t_base = -(st['margin_cm'] + spec['half_t'] * MM)

    def at(off, row=0):
        return add(mid, mul(s, off * MM), mul(t, t_base - row * PEG_ROW_GAP * MM))

    comp = face.body.parentComponent
    tl = design.timeline
    count_before = tl.count
    params = []
    notes = []
    try:
        p_board = _user_param(design, 'SkadisBoardThickness', board_t / MM,
                              'Skadis: shaft length (= board thickness)', params)
        p_lip = _user_param(design, 'SkadisLipHeight', spec['lip_h'],
                            'Skadis: lip thickness', params)
        p_ch = (_user_param(design, 'SkadisChamfer', CHAMFER, 'Skadis: lip chamfer size', params)
                if spec['chamfer'] else None)

        # 1) shafts of every hook and support peg, sketched on the face and extruded
        sk1 = comp.sketches.addWithoutEdges(face)
        sk1.name = 'Skadis - shaft sketch'
        for off in hooks:
            _draw_shaft(sk1, at(off), s, t, spec)
        for off, row in peg_list:
            _draw_shaft(sk1, at(off, row), s, t, spec)
        ext1 = _extrude(comp, sk1,
                        _all_profiles(sk1, len(hooks) + len(peg_list), spec['shaft_area']),
                        p_board.name, n)
        ext1.name = 'Skadis - shafts'

        # 2) lips: sketched on top of the shafts, extruded
        sk2 = comp.sketches.addWithoutEdges(ext1.endFaces.item(0))
        sk2.name = 'Skadis - lip sketch'
        for off in hooks:
            _draw_lip(sk2, add(at(off), mul(n, board_t)), s, t, spec)
        ext2 = _extrude(comp, sk2, _all_profiles(sk2, len(hooks), spec['lip_area']),
                        p_lip.name, n)
        ext2.name = 'Skadis - lips'

        # 3) horizontal boards only: chamfer on the top edge of the flush side of every lip
        last = ext2
        if spec['chamfer']:
            targets = [add(at(off), mul(t, -SHAFT_T / 2.0 * MM), mul(n, board_t + lip_h))
                       for off in hooks]
            edges = adsk.core.ObjectCollection.create()
            for f in ext2.endFaces:
                for e in f.edges:
                    if e.startVertex is None or e.endVertex is None:
                        continue
                    a, b = a_pt(e.startVertex), a_pt(e.endVertex)
                    m = mul(add(a, b), 0.5)
                    if any(math.sqrt(dot(sub(m, tg), sub(m, tg))) < 0.01 for tg in targets):
                        edges.add(e)
            if edges.count == len(hooks):
                ch_in = comp.features.chamferFeatures.createInput2()
                ch_in.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
                    edges, adsk.core.ValueInput.createByString(p_ch.name), True)
                last = comp.features.chamferFeatures.add(ch_in)
                last.name = 'Skadis - lip chamfer'
            else:
                notes.append('The lip chamfer was skipped: found {} of {} lip edges. '
                             'You can add it by hand (Modify > Chamfer, 3 x 3 mm).'.format(
                                 edges.count, len(hooks)))

        # one collapsed group for the whole thing
        if commit:
            try:
                group = tl.timelineGroups.add(sk1.timelineObject.index,
                                              last.timelineObject.index)
                group.name = 'Skadis ({}): {} {}{} + {} peg{}'.format(
                    spec['label'], len(hooks), spec['hook_word'], '' if len(hooks) == 1 else 's',
                    len(peg_list), '' if len(peg_list) == 1 else 's')
                group.isCollapsed = True
            except Exception:
                _log('grouping failed: ' + traceback.format_exc())
    except Exception:
        _log('create_features failed: ' + traceback.format_exc())
        _rollback(design, count_before, params)
        return 'Could not build the hooks (v{}):\n{}'.format(VERSION, traceback.format_exc())

    if not st['auto'] and len(hooks) < st['count']:
        notes.append('Only {} of the {} requested hooks fit on this edge.'.format(
            len(hooks), st['count']))
    if st['auto'] and len(hooks) == 1:
        notes.append('Only 1 hook fits on this edge (hooks sit in slots 40 mm apart). '
                     'A single hook may not hold the part.')
    if st['pegs'] and peg_fit == 0:
        notes.append('No support peg fits on the face (they sit in the slot rows '
                     'below the hooks).')
    elif st['pegs'] and not st['peg_auto'] and st['peg_count'] > peg_fit:
        notes.append('Only {} of the {} requested support pegs fit on the face.'.format(
            peg_fit, st['peg_count']))
    return '\n'.join(notes) if notes else None


def add_dialog_inputs(inputs):
    min_sel = 1
    sel = inputs.addSelectionInput(
        'face', 'Face', 'Pick the planar face that will sit flat on the SKADIS board')
    sel.addSelectionFilter('PlanarFaces')
    sel.setSelectionLimits(min_sel, 1)

    edge = inputs.addSelectionInput(
        'edge', 'Top edge', 'Pick the border of that face that is the TOP')
    edge.addSelectionFilter('LinearEdges')
    edge.setSelectionLimits(min_sel, 1)

    board = inputs.addDropDownCommandInput(
        'board', 'Board slots', adsk.core.DropDownStyles.TextListDropDownStyle)
    board.listItems.add('Horizontal (slots run left/right)', True)
    board.listItems.add('Vertical (normal: slots run up/down) - L hook', False)

    layout = inputs.addDropDownCommandInput(
        'layout', 'Hook spacing', adsk.core.DropDownStyles.TextListDropDownStyle)
    layout.listItems.add('Every 40 mm (as close as possible)', True)
    layout.listItems.add('Spread to the ends (no centre hook)', False)

    inputs.addBoolValueInput('auto', 'Automatic quantity', True, '', True)
    count = inputs.addIntegerSpinnerCommandInput('count', 'Number of hooks', 1, 20, 1, 2)
    count.isEnabled = False

    inputs.addBoolValueInput('pegs', 'Support pegs', True, '', True)
    inputs.addBoolValueInput('pegAuto', 'Automatic peg quantity (fill the face)',
                             True, '', True)
    peg_count = inputs.addIntegerSpinnerCommandInput(
        'pegCount', 'Number of support pegs', 0, 500, 1, 4)
    peg_count.isEnabled = False

    inputs.addValueInput('margin', 'Distance from top edge', 'mm',
                         adsk.core.ValueInput.createByReal(DEF_MARGIN * MM))
    inputs.addValueInput('boardT', 'Shaft length (board thickness)', 'mm',
                         adsk.core.ValueInput.createByReal(DEF_BOARD_T * MM))

    inputs.addTextBoxCommandInput(
        'info', '',
        'Hooks: one row along the top edge, either every 40 mm or spread to the ends '
        '(gaps of 40, 80, ... mm, no centre hook; the default for L hooks). Horizontal '
        'boards get the rounded 14 x 4 mm hook with its lip overhanging towards the '
        'top; vertical boards get the classic L hook (tab through the slot, lip '
        'turning down behind the board). Support pegs: the same tab without the '
        'lip, in the board\'s other slot positions below the hooks. Automatic '
        'fills every position that fits; otherwise they are placed row by row '
        'starting next to the hooks. Everything is created as normal Fusion '
        'features in one timeline group: expand it and double-click any item to '
        'edit it.',
        8, True)


def read_settings(inputs):
    return {
        'auto': inputs.itemById('auto').value,
        'count': inputs.itemById('count').value,
        'pegs': inputs.itemById('pegs').value,
        'peg_auto': inputs.itemById('pegAuto').value,
        'peg_count': inputs.itemById('pegCount').value,
        'margin_cm': inputs.itemById('margin').value,
        'board_cm': inputs.itemById('boardT').value,
        'vertical': inputs.itemById('board').selectedItem.index == 1,
        'spread': inputs.itemById('layout').selectedItem.index == 1,
    }


def read_inputs(inputs):
    """-> (face, edge, settings) or None when the selection is incomplete."""
    face_sel = inputs.itemById('face')
    edge_sel = inputs.itemById('edge')
    if face_sel.selectionCount != 1 or edge_sel.selectionCount != 1:
        return None
    face = adsk.fusion.BRepFace.cast(face_sel.selection(0).entity)
    edge = adsk.fusion.BRepEdge.cast(edge_sel.selection(0).entity)
    return face, edge, read_settings(inputs)


class ValidateHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        i = args.inputs
        args.areInputsValid = (i.itemById('face').selectionCount == 1 and
                               i.itemById('edge').selectionCount == 1)


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def notify(self, args):
        i = args.inputs
        if args.input.id == 'board':
            # L hooks default to spread-out hooks, horizontal boards to hooks every 40 mm
            vertical = args.input.selectedItem.index == 1
            i.itemById('layout').listItems.item(1 if vertical else 0).isSelected = True
        elif args.input.id == 'auto':
            i.itemById('count').isEnabled = not args.input.value
        elif args.input.id in ('pegs', 'pegAuto'):
            pegs_on = i.itemById('pegs').value
            i.itemById('pegAuto').isEnabled = pegs_on
            i.itemById('pegCount').isEnabled = pegs_on and not i.itemById('pegAuto').value


class PreviewHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            data = read_inputs(args.firingEvent.sender.commandInputs)
            if data:
                create_features(adsk.fusion.Design.cast(_app.activeProduct),
                                data[0], data[1], data[2], commit=False)
        except Exception:
            pass  # preview failures are silent; Execute reports real errors


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            design = adsk.fusion.Design.cast(_app.activeProduct)
            if design is None:
                _ui.messageBox('Please open a Design first.', 'Add Skadis')
                return
            data = read_inputs(args.firingEvent.sender.commandInputs)
            if not data:
                return
            msg = create_features(design, data[0], data[1], data[2], commit=True)
            if msg:
                _ui.messageBox(msg, 'Add Skadis')
        except Exception:
            _log('execute failed: ' + traceback.format_exc())
            _ui.messageBox('Add Skadis v{} failed:\n{}'.format(VERSION, traceback.format_exc()))


class CreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            add_dialog_inputs(cmd.commandInputs)
            for event, handler in ((cmd.validateInputs, ValidateHandler()),
                                   (cmd.inputChanged, InputChangedHandler()),
                                   (cmd.executePreview, PreviewHandler()),
                                   (cmd.execute, ExecuteHandler())):
                event.add(handler)
                _handlers.append(handler)
        except Exception:
            _ui.messageBox('Add Skadis (dialog) failed:\n{}'.format(traceback.format_exc()))


# ----------------------------------------------------------------------------
# Add-in start / stop
# ----------------------------------------------------------------------------
def run(context):
    global _app, _ui
    try:
        _app = adsk.core.Application.get()
        _ui = _app.userInterface
        res = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')

        cmd_def = _ui.commandDefinitions.itemById(CMD_ID)
        if not cmd_def:
            cmd_def = _ui.commandDefinitions.addButtonDefinition(
                CMD_ID, 'Add Skadis',
                'Adds SKADIS hooks and support pegs to a face', res)
            try:
                cmd_def.tooltipDescription = (
                    'Pick a planar face and its top edge. Hooks are placed in one row '
                    'along the top edge (in slots 40 mm apart, packed or spread to the ends) and support pegs fill the other '
                    'slot positions below. Everything is built from normal Fusion '
                    'features in one timeline group - expand it and double-click any '
                    'item to edit it.')
            except Exception:
                pass
        h = CreatedHandler()
        cmd_def.commandCreated.add(h)
        _handlers.append(h)
        _registered.append((cmd_def.commandCreated, h))

        panel = _ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
        # remove the buttons of the old custom-feature version, if they are still around
        for cid in OLD_IDS:
            old_ctrl = panel.controls.itemById(cid)
            if old_ctrl:
                old_ctrl.deleteMe()
        if not panel.controls.itemById(CMD_ID):
            ctrl = panel.controls.addCommand(cmd_def)
            ctrl.isPromotedByDefault = True
            ctrl.isPromoted = True
        _log('add-in started (v{}, {})'.format(VERSION, os.path.abspath(__file__)))
    except Exception:
        if _ui:
            _ui.messageBox('Add Skadis failed to start:\n{}'.format(traceback.format_exc()))


def stop(context):
    global _registered
    try:
        for event, handler in _registered:
            try:
                event.remove(handler)
            except Exception:
                pass
        _registered = []
        panel = _ui.workspaces.itemById(WORKSPACE_ID).toolbarPanels.itemById(PANEL_ID)
        ctrl = panel.controls.itemById(CMD_ID)
        if ctrl:
            ctrl.deleteMe()
        d = _ui.commandDefinitions.itemById(CMD_ID)
        if d:
            d.deleteMe()
    except Exception:
        if _ui:
            _ui.messageBox('Add Skadis failed to stop:\n{}'.format(traceback.format_exc()))
