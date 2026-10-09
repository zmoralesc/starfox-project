"""Shared by the settlement generators (gen_city.py, gen_town.py...): the
ground as they see it, convex polygons, Voronoi blocks, roads cut through
them, lots, kit placements fitted by measured size, lot slabs, meshes draped
on the terrain, paving the Paint layer, and the plan image.

Game coordinates throughout (x east, z south); polygons are lists of (x, z)
and are convex unless said otherwise.
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

import corneria_common as cc
from fields import chaikin

WATER_BELOW = 1.0        # ground under this is water (the sea and the lower river)


# --- The ground ---------------------------------------------------------------------
class Ground:
    """The terrain as a generator sees it: height, slope and how far the
    nearest water is, at any game (x, z)."""

    def __init__(self):
        self.h = cc.terrain_heights()
        gz, gx = np.gradient(self.h, cc.CELL)
        self.slope = np.hypot(gx, gz)
        n = cc.POINTS
        coords = -cc.HALF + np.arange(n) * cc.CELL
        # The water's edge: water grid points beside land (the nearest water
        # point to any land point is one of these).
        wet = self.h < WATER_BELOW
        land = ~wet
        beside = np.zeros_like(wet)
        beside[1:, :] |= land[:-1, :]
        beside[:-1, :] |= land[1:, :]
        beside[:, 1:] |= land[:, :-1]
        beside[:, :-1] |= land[:, 1:]
        jj, ii = np.nonzero(wet & beside)
        self.water = KDTree(len(ii))
        for k, (i, j) in enumerate(zip(ii, jj)):
            self.water.insert((coords[i], coords[j], 0.0), k)
        self.water.balance()

    def _grid(self, x, z):
        fx = (np.asarray(x, float) + cc.HALF) / cc.CELL
        fz = (np.asarray(z, float) + cc.HALF) / cc.CELL
        i = np.clip(np.floor(fx).astype(int), 0, cc.POINTS - 2)
        j = np.clip(np.floor(fz).astype(int), 0, cc.POINTS - 2)
        return i, j, np.clip(fx - i, 0, 1), np.clip(fz - j, 0, 1)

    def height(self, x, z):
        """Bilinear height (the terrain's own triangles differ by centimetres
        on the flattened ground; use surface() where that matters)."""
        i, j, u, v = self._grid(x, z)
        h = self.h
        return ((h[j, i] * (1 - u) + h[j, i + 1] * u) * (1 - v)
                + (h[j + 1, i] * (1 - u) + h[j + 1, i + 1] * u) * v)

    def surface(self, x, z):
        """The height of the game's own terrain triangles (each cell split along
        its (0,0)-(1,1) diagonal, as Terrain does)."""
        i, j, u, v = self._grid(x, z)
        h = self.h
        h00, h11 = h[j, i], h[j + 1, i + 1]
        upper = h00 + (h[j, i + 1] - h00) * u + (h11 - h[j, i + 1]) * v
        lower = h00 + (h[j + 1, i] - h00) * v + (h11 - h[j + 1, i]) * u
        return np.where(u >= v, upper, lower)

    def steepness(self, x, z):
        i, j, u, v = self._grid(x, z)
        return np.maximum.reduce([self.slope[j, i], self.slope[j, i + 1], self.slope[j + 1, i], self.slope[j + 1, i + 1]])

    def water_distance(self, x, z):
        return np.array([self.water.find((a, b, 0.0))[2] for a, b in zip(x, z)])

    def buildable(self, x, z, min_height, max_slope, water_clearance):
        x, z = np.asarray(x, float), np.asarray(z, float)
        return ((self.height(x, z) >= min_height) & (self.steepness(x, z) <= max_slope)
                & (self.water_distance(x, z) >= water_clearance))


# --- Polygons --------------------------------------------------------------------------
def clip(poly, nx, nz, d):
    """The part of a convex polygon where nx * x + nz * z <= d."""
    out = []
    count = len(poly)
    for k in range(count):
        p, q = poly[k], poly[(k + 1) % count]
        dp = nx * p[0] + nz * p[1] - d
        dq = nx * q[0] + nz * q[1] - d
        if dp <= 0:
            out.append(p)
        if (dp <= 0) != (dq <= 0):
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def area(poly):
    """Signed area (positive anticlockwise in x, z: clockwise seen from above)."""
    return 0.5 * sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))


def centroid(poly):
    a = area(poly)
    if abs(a) < 1e-6:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    cx = sum((p[0] + q[0]) * (p[0] * q[1] - q[0] * p[1]) for p, q in zip(poly, poly[1:] + poly[:1]))
    cz = sum((p[1] + q[1]) * (p[0] * q[1] - q[0] * p[1]) for p, q in zip(poly, poly[1:] + poly[:1]))
    return (cx / (6 * a), cz / (6 * a))


def oriented_box(poly):
    """The smallest rectangle round a convex polygon: centre, unit axis u (the
    long side), half length along u, half width across it."""
    best = None
    for p, q in zip(poly, poly[1:] + poly[:1]):
        dx, dz = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dz)
        if length < 1e-6:
            continue
        ux, uz = dx / length, dz / length
        us = [x * ux + z * uz for x, z in poly]
        vs = [-x * uz + z * ux for x, z in poly]
        a = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or a < best[0]:
            mu, mv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
            best = (a, (mu * ux - mv * uz, mu * uz + mv * ux), (ux, uz), (max(us) - min(us)) / 2, (max(vs) - min(vs)) / 2)
    _, c, (ux, uz), hu, hv = best
    if hv > hu:
        return c, (-uz, ux), hv, hu
    return c, (ux, uz), hu, hv


def inside_all(poly, pts):
    """Whether every point lies inside the (convex) polygon."""
    s = 1.0 if area(poly) > 0 else -1.0
    for p, q in zip(poly, poly[1:] + poly[:1]):
        ex, ez = q[0] - p[0], q[1] - p[1]
        for x, z in pts:
            if s * (ex * (z - p[1]) - ez * (x - p[0])) < -1e-6:
                return False
    return True


def rect_corners(c, u, hu, hv):
    ux, uz = u
    vx, vz = -uz, ux
    return [(c[0] + sx * hu * ux + sy * hv * vx, c[1] + sx * hu * uz + sy * hv * vz)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def inscribed(poly):
    """A large rectangle inside a convex polygon, along its oriented box:
    centre, axis u, half sizes."""
    _, u, hu, hv = oriented_box(poly)
    c = centroid(poly)

    def fits(a, b):
        return inside_all(poly, rect_corners(c, u, a, b))

    lo, hi = 0.0, 1.0
    for _ in range(12):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fits(hu * mid, hv * mid) else (lo, mid)
    a, b = hu * lo, hv * lo
    # Then each side on its own as far as it goes.
    for axis in (0, 1):
        lo2, hi2 = 1.0, 1.0 / max(lo, 1e-3)
        for _ in range(10):
            mid = (lo2 + hi2) / 2
            ok = fits(a * mid, b) if axis == 0 else fits(a, b * mid)
            lo2, hi2 = (mid, hi2) if ok else (lo2, mid)
        a, b = (a * lo2, b) if axis == 0 else (a, b * lo2)
    return c, u, a, b


def offset_out(poly, m):
    """Half-planes (nx, nz, d) of a convex polygon grown by m (shrunk if negative)."""
    s = 1.0 if area(poly) > 0 else -1.0
    planes = []
    for p, q in zip(poly, poly[1:] + poly[:1]):
        ex, ez = q[0] - p[0], q[1] - p[1]
        length = math.hypot(ex, ez)
        if length < 1e-6:
            continue
        nx, nz = s * ez / length, -s * ex / length       # outward
        planes.append((nx, nz, nx * p[0] + nz * p[1] + m))
    return planes


def split_across(poly, c, axis, t):
    """Two halves of a polygon, cut across `axis` at c + axis * t."""
    nx, nz = axis
    d = nx * c[0] + nz * c[1] + t
    return clip(poly, nx, nz, d), clip(poly, -nx, -nz, -d)


def turn_of(u):
    """The game turn that lays a piece's x along the direction u (x, z)."""
    return math.atan2(-u[1], u[0])


def densify(pts, step=40.0):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        out += [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n) for k in range(1, n + 1)]
    return out


def road_line(pts, rounds=3):
    """A road through waypoints: corners rounded off, then a point every 40 m."""
    return densify(chaikin(pts, rounds))


# --- Blocks and roads ----------------------------------------------------------------------
def voronoi_blocks(seeds, params, neighbours=14):
    """Each seed's Voronoi cell, less half the street on each side.
    seeds: [(x, z, zone)]; params(zone): a dict with "spacing" (two values,
    the cell is kept within 0.8 of the larger round its seed) and "street" (the
    street's width; a pair of neighbours gets the wider of theirs).
    Returns [(poly, zone, (x, z))]."""
    tree = KDTree(len(seeds))
    for k, (x, z, _) in enumerate(seeds):
        tree.insert((x, z, 0.0), k)
    tree.balance()
    blocks = []
    for k, (x, z, zone) in enumerate(seeds):
        d = params(zone)
        half = 0.8 * max(d["spacing"])
        poly = [(x - half, z - half), (x + half, z - half), (x + half, z + half), (x - half, z + half)]
        for _, j, dist in tree.find_n((x, z, 0.0), neighbours)[1:]:
            qx, qz, qzone = seeds[j]
            nx, nz = (qx - x) / dist, (qz - z) / dist
            street = max(d["street"], params(qzone)["street"])
            mx, mz = (x + qx) / 2, (z + qz) / 2
            poly = clip(poly, nx, nz, nx * mx + nz * mz - street / 2)
            if len(poly) < 3:
                break
        if len(poly) >= 3 and abs(area(poly)) > 100.0:
            blocks.append((poly, zone, (x, z)))
    return blocks


class Roads:
    """Roads' segments, bucketed for finding the ones near a polygon, so they
    can be cut out of blocks."""
    BUCKET = 200.0

    def __init__(self, lines, half_width):
        self.hw = half_width
        self.buckets = {}
        for line in lines:
            for a, b in zip(line, line[1:]):
                seg = (a, b)
                for key in self._keys(min(a[0], b[0]) - half_width, min(a[1], b[1]) - half_width,
                                      max(a[0], b[0]) + half_width, max(a[1], b[1]) + half_width):
                    self.buckets.setdefault(key, []).append(seg)

    def _keys(self, x0, z0, x1, z1):
        for i in range(int(math.floor(x0 / self.BUCKET)), int(math.floor(x1 / self.BUCKET)) + 1):
            for j in range(int(math.floor(z0 / self.BUCKET)), int(math.floor(z1 / self.BUCKET)) + 1):
                yield (i, j)

    def crossing(self, poly):
        """A segment whose road overlaps the polygon: (point, unit normal), or None."""
        xs, zs = [p[0] for p in poly], [p[1] for p in poly]
        seen = set()
        for key in self._keys(min(xs), min(zs), max(xs), max(zs)):
            for seg in self.buckets.get(key, ()):
                if seg in seen:
                    continue
                seen.add(seg)
                (ax, az), (bx, bz) = seg
                length = math.hypot(bx - ax, bz - az)
                ux, uz = (bx - ax) / length, (bz - az) / length
                nx, nz = -uz, ux
                ss = [(x - ax) * nx + (z - az) * nz for x, z in poly]
                ts = [(x - ax) * ux + (z - az) * uz for x, z in poly]
                if min(ss) < self.hw - 0.5 and max(ss) > -self.hw + 0.5 and max(ts) > 0 and min(ts) < length:
                    return (ax, az), (nx, nz)
        return None

    def split(self, poly):
        """The polygon with every road through it cut out: [poly]."""
        pending, done = [poly], []
        for _ in range(200):
            if not pending:
                break
            p = pending.pop()
            hit = self.crossing(p)
            if hit is None:
                done.append(p)
                continue
            (ax, az), (nx, nz) = hit
            c = nx * ax + nz * az
            for piece in (clip(p, nx, nz, c - self.hw), clip(p, -nx, -nz, -(c + self.hw))):
                if len(piece) >= 3 and abs(area(piece)) > 60.0:
                    pending.append(piece)
        return done + pending


# --- Lots ------------------------------------------------------------------------------
class Lot:
    """A piece of a block: its polygon, zone, whether it's a park (or any open
    ground), and its slab's top and bottom once fitted."""

    def __init__(self, poly, zone, park=False):
        self.poly, self.zone, self.park = poly, zone, park
        self.top = 0.0
        self.bottom = 0.0


def subdivide(poly, frontage, depth, rng, out, level=0):
    """Splits a polygon across its long side, then (if too deep) along it,
    until the pieces are about frontage x depth; appends them to `out`."""
    c, u, hu, hv = oriented_box(poly)
    if level < 14 and 2 * hu > frontage * 1.6:
        halves = split_across(poly, c, u, hu * rng.uniform(-0.25, 0.25))
    elif level < 14 and 2 * hv > depth * 2.2:
        halves = split_across(poly, c, (-u[1], u[0]), hv * rng.uniform(-0.1, 0.1))
    else:
        out.append(poly)
        return
    for h in halves:
        if len(h) >= 3 and abs(area(h)) > 20.0:
            subdivide(h, frontage, depth, rng, out, level + 1)


def lot_samples(poly):
    pts = list(poly)
    pts += [((p[0] + q[0]) / 2, (p[1] + q[1]) / 2) for p, q in zip(poly, poly[1:] + poly[:1])]
    pts.append(centroid(poly))
    return pts


def fit_lots(lots, ground, inside, buildable, curb, skirt):
    """The lots worth keeping: every sample buildable (Ground.buildable's
    keyword arguments) and the centroid `inside(x, z)` (arrays in, bools out).
    Sets each kept lot's slab: its top a curb above its highest ground, its
    bottom a skirt below its lowest."""
    if not lots:
        return []
    samples = [lot_samples(l.poly) for l in lots]
    flat = np.array([p for s in samples for p in s])
    ok = ground.buildable(flat[:, 0], flat[:, 1], **buildable)
    heights = ground.height(flat[:, 0], flat[:, 1])
    cents = np.array([centroid(l.poly) for l in lots])
    within = inside(cents[:, 0], cents[:, 1])
    kept = []
    k = 0
    for lot, s, ins in zip(lots, samples, within):
        n = len(s)
        if ins and ok[k:k + n].all():
            lot.top = float(heights[k:k + n].max()) + curb
            lot.bottom = float(heights[k:k + n].min()) - skirt
            kept.append(lot)
        k += n
    return kept


# --- Kit pieces ----------------------------------------------------------------------
def _objects(col):
    yield from col.objects
    for child in col.children:
        yield from _objects(child)


# A kit piece is a family of variants: the collection Kit_X itself and/or
# Kit_X_A, Kit_X_B... Any variant may instead be a stack, three collections
# <variant>_Base, _Shaft and _Crown: the base, then as many shafts as reach the
# height asked for, then the crown, so a tower grows by whole storeys rather
# than by stretching. Placeholders (custom property "greybox") drop out of a
# family as soon as it has one real variant.
VARIANT_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STACK_PARTS = ("Base", "Shaft", "Crown")
VARIANT_TIE = 0.2        # variants fitting within this of the best fit are picked from at random
STACK_MIN_SHAFT = 0.5    # under this many shafts' worth of height, a stack is squashed whole instead

_kit_names = None


def kit_names():
    """The names of every collection in kit.blend."""
    global _kit_names
    if _kit_names is None:
        with bpy.data.libraries.load(cc.KIT_FILE, link=True) as (src, _):
            _kit_names = set(src.collections)
    return _kit_names


def measure(col):
    """A kit collection's size (game metres: width x, height y, depth z) about
    its origin. A stack part's joint plug (an object named *_Plug: a hidden
    sleeve reaching down into the part below, so the hairline crack float
    rounding leaves at a joint shows wall, not an inner cap the ink pass would
    outline) doesn't count."""
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for o in _objects(col):
        if o.type != "MESH" or o.name.endswith("_Plug"):
            continue
        for corner in o.bound_box:
            p = o.matrix_world @ Vector(corner) - col.instance_offset
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return (hi.x - lo.x, hi.z - lo.z, hi.y - lo.y)


class Variant:
    """One variant of a piece: its collections (one, or a stack's three), its
    overall size and, for a stack, each part's height."""

    def __init__(self, name, parts):
        self.name = name
        self.parts = parts
        cols = [cc.kit_piece(p) for p in parts]
        self.greybox = any(c.get("greybox") for c in cols)
        sizes = [measure(c) for c in cols]
        self.part_size = dict(zip(parts, sizes))
        self.heights = [s[1] for s in sizes]
        self.size = (max(s[0] for s in sizes), sum(self.heights), max(s[2] for s in sizes))

    @property
    def stack(self):
        return len(self.parts) == 3

    def fit(self, size):
        """How badly this variant fits `size`: the summed log stretch of each
        axis (a stack's height costs nothing while it can grow by shafts)."""
        cost = abs(math.log(size[0] / self.size[0])) + abs(math.log(size[2] / self.size[2]))
        if not self.stack or size[1] < self._least_height():
            cost += abs(math.log(size[1] / self.size[1]))
        return cost

    def _least_height(self):
        hb, hs, hc = self.heights
        return hb + hc + STACK_MIN_SHAFT * hs

    def pieces(self, height):
        """(collection, y offset, height scale) for each part standing `height` tall."""
        if not self.stack:
            return [(self.parts[0], 0.0, height / self.size[1])]
        hb, hs, hc = self.heights
        base, shaft, crown = self.parts
        if height < self._least_height():
            k = height / self.size[1]     # too short to stack: one of each, squashed
            return [(base, 0.0, k), (shaft, hb * k, k), (crown, (hb + hs) * k, k)]
        n = max(1, round((height - hb - hc) / hs))
        k = (height - hb - hc) / (n * hs)
        out = [(base, 0.0, 1.0)] + [(shaft, hb + i * hs * k, k) for i in range(n)]
        return out + [(crown, hb + n * hs * k, 1.0)]


class Kit:
    """Kit pieces as families of variants (see VARIANT_LETTERS), linked from
    kit.blend as needed. size[name] is any collection's measured size."""

    def __init__(self, families):
        names = kit_names()
        self.variants = {}
        self.size = {}
        for family in set(families):
            found = []
            for name in [family] + [family + "_" + c for c in VARIANT_LETTERS]:
                stack = [name + "_" + p for p in STACK_PARTS]
                if name in names:
                    found.append(Variant(name, [name]))
                elif all(p in names for p in stack):
                    found.append(Variant(name, stack))
            if not found:
                raise KeyError("kit.blend has no piece " + family)
            real = [v for v in found if not v.greybox]
            self.variants[family] = real or found
            for v in self.variants[family]:
                self.size.update(v.part_size)


class Placer:
    """Collects kit placements: (collection, game transform, group). `pieces`
    maps a generator's own keys to kit piece (family) names."""

    def __init__(self, pieces, seed=0):
        self.pieces = pieces
        self.kit = Kit(pieces.values())
        self.items = []
        self.family_of = {}
        self.rng = np.random.default_rng(seed)

    def size(self, key):
        """The piece's nominal size: its first variant's. Pieces placed at
        their own size keep their footprint in every variant."""
        return self.kit.variants[self.pieces[key]][0].size

    def put(self, key, x, y, z, turn, size, group, scale=None):
        """Kit piece pieces[key] standing at (x, y, z), turned, and either
        fitted to `size` (width, height, depth: the variant that needs the
        least stretching, or one of the near-best at random), or, with size
        None, a random variant at its own size times `scale` (x, y, z; None: 1)."""
        family = self.pieces[key]
        variants = self.kit.variants[family]
        if size is None:
            v = variants[self.rng.integers(len(variants))]
            s = scale or (1.0, 1.0, 1.0)
            size = (v.size[0] * s[0], v.size[1] * s[1], v.size[2] * s[2])
        else:
            costs = [v.fit(size) for v in variants]
            near = [v for v, c in zip(variants, costs) if c <= min(costs) + VARIANT_TIE]
            v = near[self.rng.integers(len(near))]
        sx, sz = size[0] / v.size[0], size[2] / v.size[2]
        for name, dy, sy in v.pieces(size[1]):
            self.items.append((name, cc.game_transform(x, y + dy, z, turn, (sx, sy, sz)), group))
            self.family_of[name] = family

    def counts(self):
        out = {}
        for name, _, _ in self.items:
            if not name.endswith(("_Shaft", "_Crown")):    # a stack counts once
                family = self.family_of[name]
                out[family] = out.get(family, 0) + 1
        return ", ".join("%s %d" % (k[4:], v) for k, v in sorted(out.items()))


# --- Into the map ------------------------------------------------------------------------
def remove_generated(tag):
    """Removes the objects and collections a generator made (custom property
    generator = tag), and meshes left unused."""
    doomed = [o for o in bpy.data.objects if o.get("generator") == tag and o.library is None]
    meshes = [o.data for o in doomed if isinstance(o.data, bpy.types.Mesh)]
    bpy.data.batch_remove(doomed)
    bpy.data.batch_remove([m for m in meshes if m.users == 0])
    for col in [c for c in bpy.data.collections if c.get("generator") == tag and c.library is None]:
        bpy.data.collections.remove(col)


def own_collection(name, group, tag):
    col = bpy.data.collections.new(name)
    col["generator"] = tag
    bpy.data.collections[group].children.link(col)
    return col


def instantiate(placer, cols, tag):
    """Puts the placer's pieces into the map, in cols[group]."""
    for name, m, group in placer.items:
        o = cc.place(name, m, cols[group])
        o["generator"] = tag


def mesh_object(name, verts, faces, colour, tag):
    me = bpy.data.meshes.new(name)
    me.from_pydata([cc.G(*v) for v in verts], [], faces)
    me.materials.append(cc.material(colour))
    me.validate()
    o = bpy.data.objects.new(name, me)
    o["generator"] = tag
    return o


def slab_mesh(name, lots, colour, tag):
    """One object of flat slabs, one per lot: a top at lot.top and sides down
    to lot.bottom (no underside: it's never seen)."""
    verts, faces = [], []
    for lot in lots:
        poly = lot.poly
        if area(poly) > 0:          # anticlockwise in (x, z) is clockwise from above
            poly = poly[::-1]
        n = len(poly)
        base = len(verts)
        verts += [(x, lot.top, z) for x, z in poly]
        verts += [(x, lot.bottom, z) for x, z in poly]
        faces.append(tuple(range(base, base + n)))
        for k in range(n):
            q = (k + 1) % n
            faces.append((base + k, base + n + k, base + n + q, base + q))
    return mesh_object(name, verts, faces, colour, tag)


def drape(poly, ground, lift):
    """A convex polygon laid on the game's terrain triangles, `lift` above
    them: (verts, faces) in game coordinates, faces up. Every terrain
    triangle under it is clipped to it, so it follows the ground exactly."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    i0 = max(int(math.floor((min(xs) + cc.HALF) / cc.CELL)), 0)
    i1 = min(int(math.floor((max(xs) + cc.HALF) / cc.CELL)), cc.POINTS - 2)
    j0 = max(int(math.floor((min(zs) + cc.HALF) / cc.CELL)), 0)
    j1 = min(int(math.floor((max(zs) + cc.HALF) / cc.CELL)), cc.POINTS - 2)
    planes = offset_out(poly, 0.0)
    h = ground.h
    verts, faces = [], []
    for j in range(j0, j1 + 1):
        z0 = -cc.HALF + j * cc.CELL
        for i in range(i0, i1 + 1):
            x0 = -cc.HALF + i * cc.CELL
            p00 = (x0, h[j, i], z0)
            p10 = (x0 + cc.CELL, h[j, i + 1], z0)
            p01 = (x0, h[j + 1, i], z0 + cc.CELL)
            p11 = (x0 + cc.CELL, h[j + 1, i + 1], z0 + cc.CELL)
            for tri in ((p00, p10, p11), (p00, p11, p01)):
                # The triangle's plane: y = a + b x + c z.
                (ax, ay, az), (bx, by, bz), (qx, qy, qz) = tri
                det = (bx - ax) * (qz - az) - (qx - ax) * (bz - az)
                b = ((by - ay) * (qz - az) - (qy - ay) * (bz - az)) / det
                c = ((bx - ax) * (qy - ay) - (qx - ax) * (by - ay)) / det
                piece = [(t[0], t[2]) for t in tri]
                for nx, nz, d in planes:
                    piece = clip(piece, nx, nz, d)
                    if len(piece) < 3:
                        break
                if len(piece) < 3 or abs(area(piece)) < 0.01:
                    continue
                if area(piece) > 0:      # clockwise from above: Blender's up after conversion
                    piece = piece[::-1]
                base = len(verts)
                verts += [(x, ay + b * (x - ax) + c * (z - az) + lift, z) for x, z in piece]
                faces.append(tuple(range(base, base + len(piece))))
    return verts, faces


def draped_object(name, polys, ground, colour, lift, tag):
    """One object of convex polygons laid on the terrain (drape())."""
    verts, faces = [], []
    for poly in polys:
        v, f = drape(poly, ground, lift)
        base = len(verts)
        verts += v
        faces += [tuple(i + base for i in face) for face in f]
    return mesh_object(name, verts, faces, colour, tag)


def road_polys(lines, keep=None):
    """Roads [(line, half width)] as convex pieces for draping: a quad per
    segment and an octagon at each joint (so bends have no gaps). `keep(x, z)`
    can skip segments by their midpoint."""
    polys = []
    for line, hw in lines:
        joints = set()
        for k, (a, b) in enumerate(zip(line, line[1:])):
            if keep is not None and not keep((a[0] + b[0]) / 2, (a[1] + b[1]) / 2):
                continue
            dx, dz = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dz)
            if n < 0.01:
                continue
            nx, nz = -dz / n * hw, dx / n * hw
            polys.append([(a[0] + nx, a[1] + nz), (b[0] + nx, b[1] + nz), (b[0] - nx, b[1] - nz), (a[0] - nx, a[1] - nz)])
            joints.update((k, k + 1))
        for k in sorted(joints):
            if 0 < k < len(line) - 1:
                x, z = line[k]
                polys.append([(x + hw * math.cos(t), z + hw * math.sin(t))
                              for t in np.linspace(0, 2 * math.pi, 8, endpoint=False)])
    return polys


class Paving:
    """Cells to pave, marked by polygons and road lines, then written into the
    terrain's Paint layer (red). The points a generator paved are remembered in
    a boolean attribute "<tag>_paved", so a re-run first unpaves its own."""

    def __init__(self):
        self.cells = cc.POINTS - 1
        self.paved = np.zeros((self.cells, self.cells), dtype=bool)
        self.centres = -cc.HALF + (np.arange(self.cells) + 0.5) * cc.CELL

    def mark(self, planes, x0, z0, x1, z1):
        """Cells whose centres lie inside the half-planes, within the box."""
        i0, i1 = np.searchsorted(self.centres, [x0, x1])
        j0, j1 = np.searchsorted(self.centres, [z0, z1])
        if i1 <= i0 or j1 <= j0:
            return
        X, Z = np.meshgrid(self.centres[i0:i1], self.centres[j0:j1])
        inside = np.ones(X.shape, dtype=bool)
        for nx, nz, d in planes:
            inside &= nx * X + nz * Z <= d
        self.paved[j0:j1, i0:i1] |= inside

    def polygon(self, poly, margin):
        xs, zs = [p[0] for p in poly], [p[1] for p in poly]
        self.mark(offset_out(poly, margin), min(xs) - margin, min(zs) - margin, max(xs) + margin, max(zs) + margin)

    def line(self, line, half_width, keep=None):
        """A road: every segment, `half_width` either side (`keep(x, z)` can skip
        segments by their midpoint)."""
        hw = half_width
        for (ax, az), (bx, bz) in zip(line, line[1:]):
            if keep is not None and not keep((ax + bx) / 2, (az + bz) / 2):
                continue
            length = math.hypot(bx - ax, bz - az)
            ux, uz = (bx - ax) / length, (bz - az) / length
            planes = [(-uz, ux, -uz * ax + ux * az + hw), (uz, -ux, uz * ax - ux * az + hw),
                      (ux, uz, ux * bx + uz * bz + hw * 0.5), (-ux, -uz, -(ux * ax + uz * az) + hw * 0.5)]
            self.mark(planes, min(ax, bx) - hw, min(az, bz) - hw, max(ax, bx) + hw, max(az, bz) + hw)

    def write(self, ground, tag):
        """Paves the marked cells that aren't water; returns how many."""
        X, Z = np.meshgrid(self.centres, self.centres)
        paved = self.paved & (ground.height(X, Z) >= WATER_BELOW)
        # Cells to points: a point is red if any cell round it is paved.
        pts = np.zeros((cc.POINTS, cc.POINTS), dtype=bool)
        pts[:-1, :-1] |= paved
        pts[1:, :-1] |= paved
        pts[:-1, 1:] |= paved
        pts[1:, 1:] |= paved
        me = bpy.data.objects["Terrain"].data
        layer = me.color_attributes.get(cc.PAINT_ATTRIBUTE)
        if layer is None or layer.domain != "POINT":
            raise RuntimeError("the Terrain has no point-domain %s colour layer" % cc.PAINT_ATTRIBUTE)
        colors = np.empty(len(layer.data) * 4, dtype=np.float32)
        layer.data.foreach_get("color", colors)
        colors = colors.reshape(-1, 4)
        name = tag + "_paved"
        mine = me.attributes.get(name)
        if mine is not None:
            old = np.zeros(len(me.vertices), dtype=bool)
            mine.data.foreach_get("value", old)
            colors[old, 0] = 0.0
        else:
            mine = me.attributes.new(name, "BOOLEAN", "POINT")
        now = pts.reshape(-1)
        colors[now, 0] = 1.0
        layer.data.foreach_set("color", colors.reshape(-1))
        mine.data.foreach_set("value", now)
        me.update()
        return int(paved.sum())


# --- A plan, for looking at a layout ----------------------------------------------------
PLAN_COLOURS = {"lot": (0.72, 0.7, 0.66), "park": (0.3, 0.52, 0.25), "road": (0.3, 0.3, 0.32)}


def save_plan(path, ground, box, res=3.0, polygons=(), lines=(), placer=None, colours=None):
    """A top view (north up, `res` metres a pixel) of box (x0, z0, x1, z1):
    terrain shading, water, then `polygons` [(poly, colour)], `lines`
    [(line, half width, colour)] and the placer's pieces (colours[family name],
    or by height: pale blue to dark)."""
    x0, z0, x1, z1 = box
    w, h = int((x1 - x0) / res), int((z1 - z0) / res)
    xs = x0 + (np.arange(w) + 0.5) * res
    zs = z0 + (np.arange(h) + 0.5) * res
    X, Z = np.meshgrid(xs, zs)
    height = ground.height(X, Z)
    img = np.zeros((h, w, 3))
    img[:] = (0.45, 0.62, 0.36)
    img *= (0.85 + 0.15 * np.clip(height / 60.0, 0, 1))[..., None]
    img[ground.steepness(X, Z) > 0.14] = (0.6, 0.55, 0.45)
    img[height > 150] = (0.62, 0.58, 0.52)
    img[height < WATER_BELOW] = (0.2, 0.4, 0.7)

    def fill(planes, bx0, bz0, bx1, bz1, colour):
        i0, i1 = np.searchsorted(xs, [bx0, bx1])
        j0, j1 = np.searchsorted(zs, [bz0, bz1])
        if i1 <= i0 or j1 <= j0:
            return
        sx, sz = np.meshgrid(xs[i0:i1], zs[j0:j1])
        inside = np.ones(sx.shape, dtype=bool)
        for nx, nz, d in planes:
            inside &= nx * sx + nz * sz <= d
        img[j0:j1, i0:i1][inside] = colour

    def poly(p, colour):
        px, pz = [q[0] for q in p], [q[1] for q in p]
        fill(offset_out(p, 0.0), min(px), min(pz), max(px), max(pz), colour)

    for line, hw, colour in lines:
        for a, b in zip(line, line[1:]):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uz = (b[0] - a[0]) / length, (b[1] - a[1]) / length
            poly([(a[0] - uz * hw, a[1] + ux * hw), (b[0] - uz * hw, b[1] + ux * hw),
                  (b[0] + uz * hw, b[1] - ux * hw), (a[0] + uz * hw, a[1] - ux * hw)], colour)
    for p, colour in polygons:
        poly(p, colour)
    colours = colours or {}
    for name, m, _ in (placer.items if placer else ()):
        sw, sh, sd = placer.kit.size[name]
        sx, sy, sz = m.to_scale()
        hx, hz = sw * sx / 2, sd * sz / 2
        ux, uz = m[0][0] / sx, m[2][0] / sx
        c = (m[0][3], m[2][3])
        if placer.family_of[name] in colours:
            colour = colours[placer.family_of[name]]
        else:
            t = min(sh * sy / 250.0, 1.0)
            colour = (0.75 - 0.6 * t, 0.8 - 0.55 * t, 0.95 - 0.4 * t)
        if name.startswith("Kit_Tree"):
            hx = hz = hx * 0.7
        poly(rect_corners(c, (ux, uz), hx, hz), colour)
    image = bpy.data.images.new("plan", w, h)
    rgba = np.concatenate([img[::-1], np.ones((h, w, 1))], axis=2).astype(np.float32)
    image.pixels.foreach_set(rgba.reshape(-1))
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
