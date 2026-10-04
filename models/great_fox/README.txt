Great Fox III: scenery model, used by world/great_fox.tscn.

Source: downloaded by the project owner as Great_Fox_III.zip (a Sketchfab glTF export).
The download had no license or author credit. Add them here before sharing the game.

Changes from the download:
- Textures downscaled from 4096 to 1024 px (the originals totalled about 400 MB).
- The *_Normal_DirectX.png maps have "Normal Map Invert Y" on in their .import files
  (DirectX green channel -> Godot/OpenGL convention).
- Materials, meshes and the .gltf/.bin are untouched. The tilt baked into the export
  (the Sketchfab_model node) is undone by the Model node's transform in great_fox.tscn.
