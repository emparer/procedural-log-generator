# Procedural 3D Tree Log Generator

This project was developed for the **Advanced Computer Graphics** course at the Faculty of Computer and Information Science, University of Ljubljana.

The program procedurally generates 3D tree log models in Blender using Python. The generated logs include internal wood layers, tapering, ovality, global and local curvature, bark, cracked bark plates, and knots.

## Features

- Layer-based internal wood structure
- Alternating wood materials for visible rings
- Log tapering
- Oval cross-sections
- Global and local curvature
- Continuous bark mode
- Cracked bark plate mode
- Procedurally generated knots
- Local deformation of wood layers around knots
- Reproducible generation using a random seed

## Requirements

- Blender 5.x

No separate Python installation is required. The script uses Blender's built-in Python API:

- `bpy`
- `mathutils`

Because of this, the script should be run inside Blender, not with normal system Python.

## How to Run

### Option 1: Run inside Blender

1. Open Blender.
2. Go to the **Scripting** workspace.
3. Open `generate_log.py`.
4. Press **Run Script**.

The generated log object will appear in the scene.

## Parameters

The main parameters are defined at the top of `generate_log.py`.

Important parameters include:

* `LOG_LENGTH` - length of the log
* `BASE_RADIUS` - radius at the thick end
* `NUM_LAYERS` - number of internal wood layers
* `SEGMENTS_AROUND` - angular mesh resolution
* `SEGMENTS_LENGTH` - longitudinal mesh resolution
* `OVALITY_PERCENT` - cross-section ovality
* `TAPER_PERCENT` - log tapering
* `GLOBAL_CURVATURE_PERCENT` - global bending strength
* `LOCAL_CURVATURE_STRENGTH` - local centerline irregularity
* `BARK_MODE` - `"normal"` or `"cracked"`
* `NUM_KNOTS` - number of generated knots

Changing these values produces different log models.

There are more parameters but they are meant for fine tuning.
