"""Numpy helpers shared by the map's generators: noise, easing, distances to
polylines. Pure numpy (no bpy), every function works on arrays of points."""

import math

import numpy as np


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Perlin:
    """2D gradient noise over numpy arrays, roughly -1..1."""

    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        self.perm = np.concatenate([rng.permutation(256)] * 2)
        a = rng.random(256) * 2 * np.pi
        self.grad = np.stack([np.cos(a), np.sin(a)], axis=1)

    def __call__(self, x, y):
        xi = np.floor(x).astype(np.int64)
        yi = np.floor(y).astype(np.int64)
        xf, yf = x - xi, y - yi
        xi &= 255
        yi &= 255
        u = xf * xf * xf * (xf * (xf * 6 - 15) + 10)
        v = yf * yf * yf * (yf * (yf * 6 - 15) + 10)

        def corner(ix, iy, dx, dy):
            g = self.grad[self.perm[self.perm[ix] + iy]]
            return g[..., 0] * dx + g[..., 1] * dy

        n00 = corner(xi, yi, xf, yf)
        n10 = corner(xi + 1, yi, xf - 1, yf)
        n01 = corner(xi, yi + 1, xf, yf - 1)
        n11 = corner(xi + 1, yi + 1, xf - 1, yf - 1)
        return lerp(lerp(n00, n10, u), lerp(n01, n11, u), v) * 1.4


NOISES = {}


def fbm(x, z, scale, octaves=4, seed=0):
    noise = NOISES.setdefault(seed, Perlin(seed))
    total, amp, norm, f = 0.0, 1.0, 0.0, 1.0 / scale
    for k in range(octaves):
        total = total + noise(x * f + k * 17.1, z * f - k * 9.7) * amp
        norm += amp
        amp *= 0.5
        f *= 2.0
    return total / norm


def ridged(x, z, scale, octaves=5, seed=0):
    """0..1, sharp crests where the noise crosses zero."""
    noise = NOISES.setdefault(seed, Perlin(seed))
    total, amp, norm, f, weight = 0.0, 1.0, 0.0, 1.0 / scale, 1.0
    for k in range(octaves):
        n = 1.0 - np.abs(noise(x * f + k * 31.3, z * f + k * 7.9))
        n = n * n * weight
        weight = np.clip(n * 1.5, 0.0, 1.0)
        total = total + n * amp
        norm += amp
        amp *= 0.5
        f *= 2.0
    return total / norm


def line_dist(x, z, pts):
    """Distance from each point to a polyline, and how far along it (0..1) the
    nearest point lies."""
    best = np.full(x.shape, np.inf)
    along = np.zeros(x.shape)
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    start = 0.0
    for (ax, az), (bx, bz), length in zip(pts, pts[1:], lengths):
        dx, dz = bx - ax, bz - az
        t = np.clip(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz), 0.0, 1.0)
        d = np.hypot(x - ax - t * dx, z - az - t * dz)
        closer = d < best
        best = np.where(closer, d, best)
        along = np.where(closer, (start + t * length) / total, along)
        start += length
    return best, along


def chaikin(pts, rounds=3):
    """A polyline with its corners rounded off (Chaikin's corner cutting); its
    two ends stay put."""
    pts = [tuple(map(float, p)) for p in pts]
    for _ in range(rounds):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]),
                    (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = out + [pts[-1]]
    return pts

