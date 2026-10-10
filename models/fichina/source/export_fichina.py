"""Exports fichina.blend (the map's master copy) to the game: Corneria's export
script (models/corneria/source/export_corneria.py, see its docstring) run on
Fichina's map, through fichina_common.

    blender --background fichina.blend --python export_fichina.py

Writes, into models/fichina/: fichina_map.tres (the TerrainMap),
fichina_layout.tres (the PropLayout), fichina_kit.glb (the kit meshes),
fichina_props.glb (everything else in Props, by group and 500 m tile) and
fichina_markers.tres (the markers).
"""

import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichina_common as cc  # noqa: E402  (first: export_corneria then works on Fichina)

runpy.run_path(os.path.join(cc.CORNERIA_SOURCE, "export_corneria.py"), run_name="__main__")
