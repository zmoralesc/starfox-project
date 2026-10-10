"""Adds placeholder ("greybox") kit pieces to Fichina's kit.blend: plain boxes,
cylinders and cones at a piece's final name and size, so the map can be laid
out before the real models exist.

    blender --background --python greybox.py

Corneria's greybox_kit.py does the building, with this file's piece list:
see it for the rules (a piece is rebuilt only while it is a placeholder,
custom property "greybox"; real models under the same name are never
touched). The real pieces are built by kit/kit_*.py (spec: ../ASSETS.md), as
variants (Kit_X_A, _B...) that settlement.Placer prefers over the placeholder.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichina_common  # noqa: E402,F401  (first: the shared scripts then serve Fichina)
import greybox_kit  # noqa: E402

# name: (shape, size in game metres (width x, height y, depth z), palette colour)
# shape "box", "cylinder" (width = diameter), "cone" (a tree: trunk + cone),
# "frustum" (a rock), "arch".
greybox_kit.PIECES = {
    # The colony (gen_colony.py fits most of them to their lots: the sizes are
    # what a piece is at scale 1, which the real models should keep).
    "Kit_Colony_Hab": ("box", (24.0, 12.0, 16.0), "Panel"),
    "Kit_Colony_Tower": ("box", (28.0, 80.0, 28.0), "Panel"),
    "Kit_Colony_Dome": ("cylinder", (40.0, 20.0, 40.0), "Panel"),
    "Kit_Colony_Greenhouse": ("cylinder", (36.0, 18.0, 36.0), "Greenhouse"),
    "Kit_Colony_Cabin": ("box", (10.0, 6.0, 8.0), "Signal"),
    "Kit_Colony_Depot": ("box", (50.0, 14.0, 36.0), "PanelGrey"),
    "Kit_Colony_Tank": ("cylinder", (20.0, 16.0, 20.0), "Steel"),
    "Kit_Colony_Plant": ("box", (80.0, 40.0, 60.0), "DarkMetal"),
    "Kit_Colony_ClimateCenter": ("cylinder", (120.0, 240.0, 120.0), "Panel"),
    "Kit_Colony_Mast": ("box", (6.0, 50.0, 6.0), "Signal"),
    "Kit_Colony_Tube": ("box", (4.0, 4.0, 20.0), "Panel"),      # a walkway: length along z
    "Kit_Pipe": ("box", (2.0, 2.0, 20.0), "Steel"),             # a pipeline: length along z
    "Kit_Pipe_Support": ("box", (4.0, 2.0, 2.0), "DarkMetal"),
    # The spaceport and the outposts (gen_outposts.py).
    "Kit_Port_Pad": ("cylinder", (60.0, 3.0, 60.0), "Concrete"),
    "Kit_Port_Terminal": ("box", (90.0, 20.0, 40.0), "Panel"),
    "Kit_Port_Hangar": ("box", (70.0, 26.0, 60.0), "PanelGrey"),
    "Kit_Port_Tower": ("box", (16.0, 45.0, 16.0), "Concrete"),
    "Kit_Outpost_Radar": ("cylinder", (18.0, 22.0, 18.0), "Panel"),
    "Kit_Outpost_Module": ("box", (24.0, 10.0, 12.0), "Signal"),
    "Kit_Outpost_Drill": ("box", (20.0, 60.0, 20.0), "SignalYellow"),
    "Kit_Outpost_Dish": ("cylinder", (40.0, 40.0, 40.0), "Panel"),
    # Ice landmarks (gen_landmarks.py).
    "Kit_Ice_Spire": ("frustum", (30.0, 90.0, 30.0), "Ice"),
    "Kit_Ice_Arch": ("arch", (160.0, 100.0, 30.0), "Ice"),      # opening 112 x 72 m
    "Kit_Ice_Falls": ("box", (140.0, 260.0, 50.0), "Ice"),      # against a cliff, its back (-z) to the rock
    "Kit_Ice_Serac": ("frustum", (15.0, 12.0, 15.0), "Ice"),
    # The wilds (gen_wilds.py).
    "Kit_Tree_SnowPine": ("cone", (7.0, 16.0, 7.0), "Pine"),
    "Kit_Rock_Boulder": ("frustum", (8.0, 5.0, 8.0), "Rock"),
    "Kit_Rock_Outcrop": ("frustum", (30.0, 18.0, 30.0), "Rock"),
}

greybox_kit.main()
