import bpy
import math
import random
from dataclasses import dataclass
from mathutils import Vector

# ============================================================
# PARAMETERS
# ============================================================

LOG_LENGTH = 10.0          # meters, Blender units
BASE_RADIUS = 1.0          # thick end radius
NUM_LAYERS = 12

SEGMENTS_AROUND = 160
SEGMENTS_LENGTH = 64

SEED = 43

# ------------------------------------------------------------
# Ovalnost / ovality
# ovalnost = ((D - d) / D) * 100
# Example: 8 means larger diameter and smaller diameter differ by 8%.
# ------------------------------------------------------------

OVALITY_PERCENT = 6.0

# ------------------------------------------------------------
# Koničnost / tapering
# pp = (D - d) / l
# koničnost = (pp / D) * 100
# ------------------------------------------------------------

TAPER_PERCENT = 6.0

# ------------------------------------------------------------
# Bark / lubje
# ------------------------------------------------------------

# ------------------------------------------------------------
# Fractured bark plate settings
# ------------------------------------------------------------
# This mode creates separate bark plates with gaps between them.
# "normal" = old continuous bark
# "cracked" = fractured bark plates
BARK_MODE = "normal"

# Randomize plate corners so cracks do not form a perfect grid.
BARK_PLATE_CORNER_ANGLE_JITTER = 0.45
BARK_PLATE_CORNER_Z_JITTER = 0.35

# Randomly shrink/expand each plate independently.
BARK_PLATE_SIZE_RANDOMNESS = 0.25

# Random row/column offsets so vertical cracks do not align.
BARK_CRACK_ROW_OFFSET_STRENGTH = 0.65
BARK_CRACK_COLUMN_OFFSET_STRENGTH = 0.35

# Number of bark plate columns around the log.
BARK_PLATE_COLUMNS = 34

# Number of bark plate rows along the log.
BARK_PLATE_ROWS = 26

# Subdivision inside each bark plate.
# Higher values make plates bend/warp more.
BARK_PLATE_SUBDIV_ANGLE = 2
BARK_PLATE_SUBDIV_Z = 3

# Gap size between bark plates.
# 0.10 = small cracks, 0.25 = wider cracks.
BARK_PLATE_GAP_FRACTION = 0.1

# Random outward expansion of bark plates.
BARK_PLATE_RANDOM_RAISE = 0.055

# Random sideways/z displacement of individual plates.
BARK_PLATE_RANDOM_TANGENT_SHIFT = 0.025
BARK_PLATE_RANDOM_Z_SHIFT = 0.055

# Extra roughness inside each plate.
BARK_PLATE_INTERNAL_ROUGHNESS = 0.025

# Extra detail only for cracked bark.
# Higher values = more geometry and more visible cracks.
BARK_CRACKED_ANGLE_MULTIPLIER = 2
BARK_CRACKED_LENGTH_MULTIPLIER = 2

# Width of vertical crack grooves around the bark.
# Smaller = thinner cracks, larger = wider cracks.
BARK_CRACK_WIDTH = 0.18

# How deep cracks cut inward.
BARK_CRACK_DEPTH = 0.075

# How much bark plates are raised outward between cracks.
BARK_PLATE_RAISE = 0.045

# How broken/uneven the plates are along z.
BARK_PLATE_LENGTH_VARIATION = 0.135
BARK_THICKNESS = 0.04
BARK_CRACK_STRENGTH = 0.06
BARK_CRACK_FREQUENCY = 16
BARK_RELIEF_STRENGTH = 0.03

# ------------------------------------------------------------
# Local curvature / local irregularity
# ------------------------------------------------------------

LOCAL_CURVATURE_STRENGTH = 0.065
LOCAL_CURVATURE_FREQUENCY = 8.0

# ------------------------------------------------------------
# Global curvature / krivost
# krivost = h / l
# stopnja krivosti = (h / l) * 100
# ------------------------------------------------------------

GLOBAL_CURVATURE_PERCENT = 7.0
GLOBAL_BEND_COUNT = 3       # 1 = one arc/U shape, 2 = S-like shape

# ------------------------------------------------------------
# Ring noise
# Must be bounded so layers do not cross.
# ------------------------------------------------------------

LAYER_NOISE_AMOUNT = 0.18
LAYER_Z_VARIATION = 1.2
LAYER_ANGLE_VARIATION = 5

# ------------------------------------------------------------
# Knots / grče
# ------------------------------------------------------------

NUM_KNOTS = 6
KNOT_PULLED_LAYER_COUNT = 4
KNOT_RADIUS_MIN = 0.12
KNOT_RADIUS_MAX = 0.32
KNOT_LENGTH_OUTSIDE_MIN = 0.25
KNOT_LENGTH_OUTSIDE_MAX = 0.65
KNOT_INFLUENCE_Z = 1.0
KNOT_INFLUENCE_ANGLE = 0.75
KNOT_RING_BEND_STRENGTH = 0.35
KNOT_SURFACE_BUMP = 0.16
# ------------------------------------------------------------
# Knot local wrap / fiber avoidance
# ------------------------------------------------------------
# These push nearby layer vertices around the knot in local tangent/z space.
# Larger values = wood strands bend more around the grča.
KNOT_LOCAL_WRAP_STRENGTH = 0.35
KNOT_LOCAL_Z_WRAP_STRENGTH = 0.10

# How much stronger the effect gets for outer layers.
KNOT_WRAP_OUTER_LAYER_MULTIPLIER = 2.0

# Inner layers before the knot origin are not affected.
# Pulled layers and outer layers are affected.
KNOT_MIN_NORMAL_COMPONENT = 0.55


# ============================================================
# CLEAN SCENE
# ============================================================

#bpy.ops.object.select_all(action="SELECT")
#bpy.ops.object.delete()


# ============================================================
# MATERIALS
# ============================================================

def make_material(name, color):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    return mat


bark_mat = make_material("Dark bark", (0.16, 0.08, 0.035, 1.0))
wood_light_mat = make_material("Light wood", (0.72, 0.48, 0.24, 1.0))
wood_dark_mat = make_material("Dark wood ring", (0.45, 0.25, 0.10, 1.0))
core_mat = make_material("Heartwood core", (0.35, 0.16, 0.07, 1.0))

knot_bark_mat = make_material("Knot dark outer wood", (0.20, 0.09, 0.035, 1.0))
knot_light_mat = make_material("Knot light ring", (0.58, 0.34, 0.13, 1.0))
knot_dark_mat = make_material("Knot dark ring", (0.30, 0.13, 0.045, 1.0))


MATERIALS = {
    "bark": bark_mat,
    "wood_light": wood_light_mat,
    "wood_dark": wood_dark_mat,
    "core": core_mat,
}


# ============================================================
# UTILS
# ============================================================

def angular_distance(a, b):
    """
    Smallest angular distance between two angles.
    """
    diff = (a - b + math.pi) % (2.0 * math.pi) - math.pi
    return diff


def smooth_falloff(x):
    """
    Smooth falloff from 1 to 0.
    x should be in [0, 1].
    """
    x = max(0.0, min(1.0, x))
    return 1.0 - (x * x * (3.0 - 2.0 * x))


def make_basis_from_direction(direction):
    """
    Creates two perpendicular vectors around a direction.
    Used for knot cross-sections.
    """
    direction = direction.normalized()

    if abs(direction.dot(Vector((0, 0, 1)))) < 0.9:
        helper = Vector((0, 0, 1))
    else:
        helper = Vector((1, 0, 0))

    u = direction.cross(helper).normalized()
    v = direction.cross(u).normalized()

    return u, v


# ============================================================
# SMOOTH PROCEDURAL NOISE HELPERS
# ============================================================

class SmoothSineNoise1D:
    def __init__(self, seed, modes=4):
        rng = random.Random(seed)
        self.terms = []

        for _ in range(modes):
            freq = rng.uniform(0.5, 2.5)
            phase = rng.uniform(0.0, math.tau)
            amp = rng.uniform(0.4, 1.0)
            self.terms.append((freq, phase, amp))

        self.amp_sum = sum(abs(t[2]) for t in self.terms)

    def sample(self, t):
        value = 0.0

        for freq, phase, amp in self.terms:
            value += amp * math.sin(math.tau * freq * t + phase)

        return value / self.amp_sum


class RingBoundaryNoise:
    def __init__(
        self,
        num_layers,
        seed,
        angle_variation=5,
        z_variation=1.2,
        modes_per_boundary=5
    ):
        self.num_layers = num_layers
        self.boundary_terms = {}

        rng = random.Random(seed)

        for boundary_index in range(1, num_layers):
            terms = []

            for _ in range(modes_per_boundary):
                angle_freq = rng.randint(2, angle_variation + 3)
                z_freq = rng.uniform(0.3, z_variation)
                phase = rng.uniform(0.0, math.tau)
                amp = rng.uniform(0.4, 1.0)

                terms.append((angle_freq, z_freq, phase, amp))

            amp_sum = sum(abs(t[3]) for t in terms)
            self.boundary_terms[boundary_index] = (terms, amp_sum)

    def sample(self, boundary_index, angle, z_normalized):
        terms, amp_sum = self.boundary_terms[boundary_index]

        value = 0.0

        for angle_freq, z_freq, phase, amp in terms:
            value += amp * math.sin(
                angle_freq * angle +
                math.tau * z_freq * z_normalized +
                phase
            )

        return value / amp_sum


# ============================================================
# REAL LAYER-BASED LOG MODEL
# ============================================================

@dataclass
class Knot:
    z: float
    angle: float
    direction: Vector
    radius: float
    length_outside: float
    origin_layer: int
    pulled_layer_count: int
    influence_z: float
    influence_angle: float
    ring_bend_strength: float
    surface_bump: float

    def angular_falloff(self, angle):
        d = abs(angular_distance(angle, self.angle))
        return smooth_falloff(d / self.influence_angle)

    def z_falloff(self, z):
        d = abs(z - self.z)
        return smooth_falloff(d / self.influence_z)

    def influence(self, angle, z):
        return self.angular_falloff(angle) * self.z_falloff(z)


def material_for_layer(layer_index):
    if layer_index == 0:
        return "core"
    elif layer_index % 2 == 0:
        return "wood_light"
    else:
        return "wood_dark"


def add_materials_to_object(obj):
    obj.data.materials.append(MATERIALS["bark"])
    obj.data.materials.append(MATERIALS["wood_light"])
    obj.data.materials.append(MATERIALS["wood_dark"])
    obj.data.materials.append(MATERIALS["core"])


def material_lookup():
    return {
        "bark": 0,
        "wood_light": 1,
        "wood_dark": 2,
        "core": 3,
    }


# ============================================================
# FORMULAS / SHAPE FUNCTIONS
# ============================================================

def z_to_t(z):
    return (z + LOG_LENGTH / 2.0) / LOG_LENGTH


def radius_at_z(z):
    """
    Koničnost / taper.

    pp = (D - d) / l
    koničnost = (pp / D) * 100

    TAPER_PERCENT is interpreted as koničnost in percent.
    """

    t = z_to_t(z)

    D_base = BASE_RADIUS * 2.0
    pp = D_base * (TAPER_PERCENT / 100.0)
    diameter_drop = pp * LOG_LENGTH

    D_at_z = D_base - diameter_drop * t

    return max(0.05, D_at_z / 2.0)


def oval_radii(radius):
    """
    Ovalnost = ((D - d) / D) * 100

    D = larger diameter
    d = smaller diameter

    We use x as the larger direction and y as the smaller direction.
    """

    rx = radius
    ry = radius * (1.0 - OVALITY_PERCENT / 100.0)
    return rx, ry


def global_curvature_offset(z):
    """
    Krivost = h / l
    stopnja krivosti = (h / l) * 100

    GLOBAL_BEND_COUNT:
    1 = one arc / U-like curve
    2 = S-like curve
    """

    t = z_to_t(z)
    h = LOG_LENGTH * (GLOBAL_CURVATURE_PERCENT / 100.0)

    x = h * math.sin(math.pi * GLOBAL_BEND_COUNT * t)
    y = 0.0

    return Vector((x, y, 0.0))


local_noise_x = SmoothSineNoise1D(SEED + 111, modes=4)
local_noise_y = SmoothSineNoise1D(SEED + 222, modes=4)


def local_curvature_offset(z):
    """
    Small local variation of the log axis.
    """

    t = z_to_t(z)

    x = LOCAL_CURVATURE_STRENGTH * local_noise_x.sample(t * LOCAL_CURVATURE_FREQUENCY)
    y = LOCAL_CURVATURE_STRENGTH * local_noise_y.sample(t * LOCAL_CURVATURE_FREQUENCY)

    return Vector((x, y, 0.0))


def centerline_at_z(z):
    return Vector((0.0, 0.0, z)) + global_curvature_offset(z) + local_curvature_offset(z)


# ============================================================
# NON-CROSSING LAYER BOUNDARIES
# ============================================================

layer_noise = RingBoundaryNoise(
    num_layers=NUM_LAYERS,
    seed=SEED + 333,
    angle_variation=LAYER_ANGLE_VARIATION,
    z_variation=LAYER_Z_VARIATION,
    modes_per_boundary=5
)


def boundary_radius_normalized(boundary_index, angle, z, knots):
    """
    Returns normalized radius of a layer boundary.

    boundary_index:
    0 = center
    NUM_LAYERS = outside of wood, before bark

    Values are kept ordered by using small bounded noise.
    """

    if boundary_index <= 0:
        return 0.0

    if boundary_index >= NUM_LAYERS:
        return 1.0

    layer_spacing = 1.0 / NUM_LAYERS
    base_radius = boundary_index * layer_spacing

    noise = layer_noise.sample(
        boundary_index=boundary_index,
        angle=angle,
        z_normalized=z_to_t(z)
    )

    max_offset = LAYER_NOISE_AMOUNT * layer_spacing
    r = base_radius + noise * max_offset

    # Knot influence:
    # pulled layers and outer layers are displaced near the knot.
    for knot in knots:
        influence = knot.influence(angle, z)

        if influence <= 0.0:
            continue

        pulled_start = knot.origin_layer
        pulled_end = knot.origin_layer + knot.pulled_layer_count - 1

        if boundary_index < pulled_start:
            continue

        if pulled_start <= boundary_index <= pulled_end + 1:
            local_t = (boundary_index - pulled_start) / max(1, knot.pulled_layer_count)
            r += (
                knot.ring_bend_strength *
                layer_spacing *
                influence *
                (1.0 + 0.45 * local_t)
            )

        elif boundary_index > pulled_end + 1:
            outer_t = (boundary_index - pulled_end) / max(
                1,
                NUM_LAYERS - pulled_end
            )
            r += (
                knot.ring_bend_strength *
                layer_spacing *
                influence *
                (0.45 + 0.35 * outer_t)
            )

    return max(0.0, min(1.0, r))

def knot_local_displacement(point, boundary_index, angle, z, knots):
    """
    Pushes vertices away from the grča axis.

    Instead of pushing only in tangent/z directions, this finds the closest
    point on the knot axis and pushes the vertex away from that point.

    This means wood layers flow around the knot volume.
    """

    result = Vector((point.x, point.y, point.z))

    for knot in knots:
        pulled_start = knot.origin_layer
        pulled_end = knot.origin_layer + knot.pulled_layer_count - 1

        # Older inner layers existed before the branch.
        # Do not deform them.
        if boundary_index < pulled_start:
            continue

        root_point, end_point = knot_axis_points(knot)

        axis = end_point - root_point
        axis_length = axis.length

        if axis_length <= 0.0001:
            continue

        axis_dir = axis.normalized()

        # Project current vertex onto the knot axis.
        rel = result - root_point
        along = rel.dot(axis_dir)

        # Clamp projection to the actual knot segment.
        along_clamped = max(0.0, min(axis_length, along))

        closest_point = root_point + axis_dir * along_clamped

        away_vec = result - closest_point
        distance_from_axis = away_vec.length

        if distance_from_axis <= 0.0001:
            # Rare case: point is exactly on the axis.
            # Use surface normal as fallback.
            away_dir = Vector((
                math.cos(knot.angle),
                math.sin(knot.angle),
                0.0
            )).normalized()
        else:
            away_dir = away_vec.normalized()

        # Influence along knot length.
        t_axis = along_clamped / axis_length

        # Knot is strongest inside/near surface, weaker at outside tip.
        axis_falloff = smooth_falloff(abs(t_axis - 0.45) / 0.75)

        # Influence by distance from knot axis.
        # This radius is the "avoidance area" around the grča.
        avoid_radius = knot.radius * 3.0

        distance_falloff = smooth_falloff(distance_from_axis / max(avoid_radius, 0.0001))

        # Also limit by z/angle neighborhood, so it does not deform the whole log.
        local_influence = knot.influence(angle, z)

        influence = axis_falloff * distance_falloff * local_influence

        if influence <= 0.0:
            continue

        # Pulled layers and outer layers are affected.
        # Outer layers bend more because they grew around the grča.
        if pulled_start <= boundary_index <= pulled_end + 1:
            layer_factor = 1.0
        else:
            outer_t = (boundary_index - pulled_end) / max(1, NUM_LAYERS - pulled_end)
            layer_factor = 1.0 + KNOT_WRAP_OUTER_LAYER_MULTIPLIER * max(0.0, outer_t)

        # Strongest push amount.
        push_amount = (
            KNOT_LOCAL_WRAP_STRENGTH *
            knot.radius *
            influence *
            layer_factor
        )

        result += away_dir * push_amount

    return result

def knot_axis_points(knot):
    """
    Returns root_point and end_point of the grča axis.

    The root starts at the chosen origin layer.
    The end goes outward from the log surface.
    """

    center = centerline_at_z(knot.z)

    surface_normal = Vector((
        math.cos(knot.angle),
        math.sin(knot.angle),
        0.0
    )).normalized()

    base_radius = radius_at_z(knot.z)
    wood_radius = max(0.01, base_radius - BARK_THICKNESS)

    # Root starts at the chosen layer inside the log.
    origin_fraction = knot.origin_layer / NUM_LAYERS
    origin_radius = wood_radius * origin_fraction

    rx_origin, ry_origin = oval_radii(origin_radius)
    root_point = Vector((
        center.x + rx_origin * math.cos(knot.angle),
        center.y + ry_origin * math.sin(knot.angle),
        knot.z
    ))

    # Surface point where the grča exits the log.
    rx_surface, ry_surface = oval_radii(base_radius)
    surface_point = Vector((
        center.x + rx_surface * math.cos(knot.angle),
        center.y + ry_surface * math.sin(knot.angle),
        knot.z
    ))

    end_point = surface_point + knot.direction * knot.length_outside

    return root_point, end_point


def point_on_layer_boundary(boundary_index, angle, z, knots, bark_extra=0.0):
    """
    Creates a point on a layer boundary after:
    - tapering / koničnost
    - ovality / ovalnost
    - global curvature / krivost
    - local curvature
    - layer noise
    - knot wrapping
    - optional bark relief

    The important new part:
    vertices near knots are pushed around the grča locally, so the layer
    strands curve around it instead of remaining straight.
    """

    center = centerline_at_z(z)

    base_radius = radius_at_z(z)

    # Wood radius excludes bark.
    wood_radius = max(0.01, base_radius - BARK_THICKNESS)

    if boundary_index == NUM_LAYERS:
        r_norm = 1.0
    else:
        r_norm = boundary_radius_normalized(boundary_index, angle, z, knots)

    radius = wood_radius * r_norm + bark_extra

    rx, ry = oval_radii(radius)

    x = center.x + rx * math.cos(angle)
    y = center.y + ry * math.sin(angle)

    point = Vector((x, y, z))

    # Do not wrap the exact center tiny core too much.
    # Everything from the knot origin layer outward can bend around grče.
    point = knot_local_displacement(
        point=point,
        boundary_index=boundary_index,
        angle=angle,
        z=z,
        knots=knots
    )

    return point


def bark_relief_normal(angle, z):
    """
    Current smoother bark relief.
    """

    t = z_to_t(z)

    vertical_stripes = math.sin(angle * BARK_CRACK_FREQUENCY + t * 7.0)
    secondary = math.sin(angle * (BARK_CRACK_FREQUENCY * 0.37) - t * 11.0)

    crack_value = max(0.0, vertical_stripes * 0.7 + secondary * 0.3)

    return BARK_RELIEF_STRENGTH * crack_value * BARK_CRACK_STRENGTH / 0.06


def bark_relief_cracked(angle, z):
    """
    Strong cracked bark relief.

    Idea:
    - create repeated vertical crack grooves around the log
    - grooves are pushed inward
    - bark plates between grooves are raised outward
    - z variation breaks the grooves so they are not perfectly straight
    """

    t = z_to_t(z)

    # This creates vertical stripe coordinates.
    stripe = (angle * BARK_CRACK_FREQUENCY / math.tau) % 1.0

    # Distance to nearest crack center.
    dist_to_crack = min(stripe, 1.0 - stripe)

    # Crack mask:
    # 1 near crack center, 0 away from crack.
    crack_zone = 1.0 - smooth_falloff(dist_to_crack / max(BARK_CRACK_WIDTH, 0.0001))

    # Plate mask:
    # 1 away from cracks, 0 near cracks.
    plate_zone = 1.0 - crack_zone

    # Break up the plates along z so they look like bark chunks.
    z_break = (
        0.55 * math.sin(t * 42.0 + angle * 3.0) +
        0.35 * math.sin(t * 93.0 - angle * 5.7) +
        0.10 * math.sin(t * 157.0 + angle * 11.0)
    )

    # Small angular roughness.
    angular_rough = (
        0.5 * math.sin(angle * 31.0 + t * 8.0) +
        0.5 * math.sin(angle * 67.0 - t * 13.0)
    )

    plate_variation = BARK_PLATE_LENGTH_VARIATION * z_break
    rough_variation = BARK_RELIEF_STRENGTH * 0.45 * angular_rough

    # Positive means raised, negative means recessed.
    relief = (
        plate_zone * (BARK_PLATE_RAISE + plate_variation + rough_variation)
        - crack_zone * BARK_CRACK_DEPTH
    )

    return relief


def bark_relief(angle, z):
    if BARK_MODE == "cracked":
        return bark_relief_cracked(angle, z)

    return bark_relief_normal(angle, z)


# ============================================================
# KNOT GENERATION
# ============================================================

def sample_knot_direction(angle, rng):
    normal = Vector((math.cos(angle), math.sin(angle), 0.0)).normalized()
    tangent = Vector((-math.sin(angle), math.cos(angle), 0.0)).normalized()
    z_axis = Vector((0.0, 0.0, 1.0))

    for _ in range(100):
        normal_strength = rng.uniform(KNOT_MIN_NORMAL_COMPONENT, 1.0)
        tangent_strength = rng.uniform(-0.25, 0.25)
        z_strength = rng.uniform(-0.35, 0.35)

        direction = (
            normal * normal_strength +
            tangent * tangent_strength +
            z_axis * z_strength
        ).normalized()

        if direction.dot(normal) >= KNOT_MIN_NORMAL_COMPONENT:
            return direction

    return normal


def generate_knots():
    rng = random.Random(SEED + 900)
    knots = []

    for _ in range(NUM_KNOTS):
        # Avoid very ends of log.
        z = rng.uniform(-LOG_LENGTH * 0.35, LOG_LENGTH * 0.35)
        angle = rng.uniform(0.0, math.tau)

        # Origin should not be too close to center or outermost layer.
        max_origin = max(2, NUM_LAYERS - KNOT_PULLED_LAYER_COUNT - 2)
        origin_layer = rng.randint(2, max_origin)

        radius = rng.uniform(KNOT_RADIUS_MIN, KNOT_RADIUS_MAX)
        length_outside = rng.uniform(KNOT_LENGTH_OUTSIDE_MIN, KNOT_LENGTH_OUTSIDE_MAX)

        direction = sample_knot_direction(angle, rng)

        knot = Knot(
            z=z,
            angle=angle,
            direction=direction,
            radius=radius,
            length_outside=length_outside,
            origin_layer=origin_layer,
            pulled_layer_count=KNOT_PULLED_LAYER_COUNT,
            influence_z=KNOT_INFLUENCE_Z,
            influence_angle=KNOT_INFLUENCE_ANGLE,
            ring_bend_strength=KNOT_RING_BEND_STRENGTH,
            surface_bump=KNOT_SURFACE_BUMP
        )

        knots.append(knot)

    return knots


KNOTS = generate_knots()


# ============================================================
# CREATE REAL LAYER SHELLS
# ============================================================

def append_layer_shell(vertices, faces, face_materials, layer_index, knots):
    """
    Creates one actual mesh shell for one wood layer.

    The layer is between boundary layer_index and layer_index + 1.
    """

    z_min = -LOG_LENGTH / 2.0
    z_max = LOG_LENGTH / 2.0

    material_name = material_for_layer(layer_index)

    # Avoid degenerate center hole for the core.
    inner_boundary = layer_index
    outer_boundary = layer_index + 1

    start_index = len(vertices)

    # For every z and angle, create outer and inner boundary vertices.
    for iz in range(SEGMENTS_LENGTH + 1):
        tz = iz / SEGMENTS_LENGTH
        z = z_min + tz * LOG_LENGTH

        for ia in range(SEGMENTS_AROUND):
            angle = math.tau * ia / SEGMENTS_AROUND

            outer_p = point_on_layer_boundary(
                outer_boundary,
                angle,
                z,
                knots
            )

            if inner_boundary == 0:
                # Tiny non-zero radius avoids degenerate geometry at center.
                center = centerline_at_z(z)
                tiny_radius = radius_at_z(z) * 0.002
                rx, ry = oval_radii(tiny_radius)
                inner_p = Vector((
                    center.x + rx * math.cos(angle),
                    center.y + ry * math.sin(angle),
                    z
                ))
            else:
                inner_p = point_on_layer_boundary(
                    inner_boundary,
                    angle,
                    z,
                    knots
                )

            vertices.append((outer_p.x, outer_p.y, outer_p.z))
            vertices.append((inner_p.x, inner_p.y, inner_p.z))

    row_size = SEGMENTS_AROUND * 2

    # Side faces along length: outer and inner surface.
    for iz in range(SEGMENTS_LENGTH):
        for ia in range(SEGMENTS_AROUND):
            outer_a = start_index + iz * row_size + ia * 2
            inner_a = outer_a + 1

            outer_b = start_index + iz * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_b = outer_b + 1

            outer_c = start_index + (iz + 1) * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_c = outer_c + 1

            outer_d = start_index + (iz + 1) * row_size + ia * 2
            inner_d = outer_d + 1

            # Outer surface of layer.
            faces.append((outer_a, outer_b, outer_c, outer_d))
            face_materials.append(material_name)

            # Inner surface of layer.
            faces.append((inner_b, inner_a, inner_d, inner_c))
            face_materials.append(material_name)

    # End faces: annular faces at both ends.
    def add_annular_end(iz, flip):
        for ia in range(SEGMENTS_AROUND):
            outer_a = start_index + iz * row_size + ia * 2
            inner_a = outer_a + 1

            outer_b = start_index + iz * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_b = outer_b + 1

            if flip:
                faces.append((inner_a, outer_a, outer_b, inner_b))
            else:
                faces.append((inner_a, inner_b, outer_b, outer_a))

            face_materials.append(material_name)

    add_annular_end(0, flip=True)
    add_annular_end(SEGMENTS_LENGTH, flip=False)


def append_bark_shell(vertices, faces, face_materials, knots):
    """
    Adds lubje/bark.

    BARK_MODE:
    - "normal": continuous bark shell
    - "cracked": broken bark plates

    In cracked mode:
    - bark is not one continuous surface
    - each plate is slightly expanded/randomly displaced
    - gaps/cracks appear between plates
    - every plate edge connects down to the layer below
    """

    if BARK_MODE == "cracked":
        append_cracked_bark_shell(vertices, faces, face_materials, knots)
    else:
        append_normal_bark_shell(vertices, faces, face_materials, knots)


def append_normal_bark_shell(vertices, faces, face_materials, knots):
    """
    Old continuous bark version.
    """

    z_min = -LOG_LENGTH / 2.0
    start_index = len(vertices)

    for iz in range(SEGMENTS_LENGTH + 1):
        tz = iz / SEGMENTS_LENGTH
        z = z_min + tz * LOG_LENGTH

        for ia in range(SEGMENTS_AROUND):
            angle = math.tau * ia / SEGMENTS_AROUND

            inner_p = point_on_layer_boundary(
                NUM_LAYERS,
                angle,
                z,
                knots,
                bark_extra=0.0
            )

            relief = bark_relief(angle, z)

            bump = 0.0
            for knot in knots:
                bump += knot.surface_bump * knot.influence(angle, z)

            outer_p = point_on_layer_boundary(
                NUM_LAYERS,
                angle,
                z,
                knots,
                bark_extra=BARK_THICKNESS + relief + bump
            )

            vertices.append((outer_p.x, outer_p.y, outer_p.z))
            vertices.append((inner_p.x, inner_p.y, inner_p.z))

    row_size = SEGMENTS_AROUND * 2

    for iz in range(SEGMENTS_LENGTH):
        for ia in range(SEGMENTS_AROUND):
            outer_a = start_index + iz * row_size + ia * 2
            inner_a = outer_a + 1

            outer_b = start_index + iz * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_b = outer_b + 1

            outer_c = start_index + (iz + 1) * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_c = outer_c + 1

            outer_d = start_index + (iz + 1) * row_size + ia * 2
            inner_d = outer_d + 1

            faces.append((outer_a, outer_b, outer_c, outer_d))
            face_materials.append("bark")

            faces.append((inner_b, inner_a, inner_d, inner_c))
            face_materials.append("bark")

    def add_bark_end(iz, flip):
        for ia in range(SEGMENTS_AROUND):
            outer_a = start_index + iz * row_size + ia * 2
            inner_a = outer_a + 1

            outer_b = start_index + iz * row_size + ((ia + 1) % SEGMENTS_AROUND) * 2
            inner_b = outer_b + 1

            if flip:
                faces.append((inner_a, outer_a, outer_b, inner_b))
            else:
                faces.append((inner_a, inner_b, outer_b, outer_a))

            face_materials.append("bark")

    add_bark_end(0, flip=True)
    add_bark_end(SEGMENTS_LENGTH, flip=False)


def append_cracked_bark_shell(vertices, faces, face_materials, knots):
    """
    Fractured bark with irregular plates.

    Instead of a regular grid of rectangular bark plates, this creates
    randomly warped plates. Cracks do not line up perfectly in angle or z.

    Each plate:
    - has four randomly shifted corners
    - has a raised outer surface
    - has side walls down to the base bark/wood surface
    - leaves visible gaps between neighboring plates
    """

    z_min = -LOG_LENGTH / 2.0
    z_max = LOG_LENGTH / 2.0

    plate_angle_size = math.tau / BARK_PLATE_COLUMNS
    plate_z_size = LOG_LENGTH / BARK_PLATE_ROWS

    base_angle_gap = plate_angle_size * BARK_PLATE_GAP_FRACTION
    base_z_gap = plate_z_size * BARK_PLATE_GAP_FRACTION

    for pz in range(BARK_PLATE_ROWS):
        # Row offset prevents long vertical crack lines.
        row_rng = random.Random(SEED + 8100 + pz)
        row_angle_offset = row_rng.uniform(
            -plate_angle_size * BARK_CRACK_ROW_OFFSET_STRENGTH,
            plate_angle_size * BARK_CRACK_ROW_OFFSET_STRENGTH
        )

        for pa in range(BARK_PLATE_COLUMNS):
            plate_seed = SEED + 9000 + pz * 1000 + pa
            prng = random.Random(plate_seed)

            # Column/plate offset prevents horizontal alignment.
            column_z_offset = prng.uniform(
                -plate_z_size * BARK_CRACK_COLUMN_OFFSET_STRENGTH,
                plate_z_size * BARK_CRACK_COLUMN_OFFSET_STRENGTH
            )

            # Random plate scale.
            size_scale_a = prng.uniform(
                1.0 - BARK_PLATE_SIZE_RANDOMNESS,
                1.0 + BARK_PLATE_SIZE_RANDOMNESS
            )
            size_scale_z = prng.uniform(
                1.0 - BARK_PLATE_SIZE_RANDOMNESS,
                1.0 + BARK_PLATE_SIZE_RANDOMNESS
            )

            angle_gap = base_angle_gap * prng.uniform(0.6, 1.5)
            z_gap = base_z_gap * prng.uniform(0.6, 1.5)

            # Base rectangular cell.
            cell_angle0 = pa * plate_angle_size + row_angle_offset
            cell_angle1 = (pa + 1) * plate_angle_size + row_angle_offset

            cell_z0 = z_min + pz * plate_z_size + column_z_offset
            cell_z1 = z_min + (pz + 1) * plate_z_size + column_z_offset

            # Center and scaled size.
            angle_center = (cell_angle0 + cell_angle1) * 0.5
            z_center = (cell_z0 + cell_z1) * 0.5

            half_angle = (plate_angle_size * size_scale_a - angle_gap) * 0.5
            half_z = (plate_z_size * size_scale_z - z_gap) * 0.5

            if half_angle <= 0.001 or half_z <= 0.001:
                continue

            # Four rough corners before jitter.
            a0 = angle_center - half_angle
            a1 = angle_center + half_angle
            z0 = z_center - half_z
            z1 = z_center + half_z

            # Clamp z so plates stay on the log.
            z0 = max(z_min, z0)
            z1 = min(z_max, z1)

            if z1 <= z0:
                continue

            # Corner jitter amount.
            corner_angle_jitter = plate_angle_size * BARK_PLATE_CORNER_ANGLE_JITTER
            corner_z_jitter = plate_z_size * BARK_PLATE_CORNER_Z_JITTER

            # Four corners:
            # bottom-left, bottom-right, top-right, top-left
            corners = [
                Vector((
                    a0 + prng.uniform(-corner_angle_jitter, corner_angle_jitter),
                    0.0,
                    z0 + prng.uniform(-corner_z_jitter, corner_z_jitter)
                )),
                Vector((
                    a1 + prng.uniform(-corner_angle_jitter, corner_angle_jitter),
                    0.0,
                    z0 + prng.uniform(-corner_z_jitter, corner_z_jitter)
                )),
                Vector((
                    a1 + prng.uniform(-corner_angle_jitter, corner_angle_jitter),
                    0.0,
                    z1 + prng.uniform(-corner_z_jitter, corner_z_jitter)
                )),
                Vector((
                    a0 + prng.uniform(-corner_angle_jitter, corner_angle_jitter),
                    0.0,
                    z1 + prng.uniform(-corner_z_jitter, corner_z_jitter)
                )),
            ]

            # Keep z clamped after jitter.
            for c in corners:
                c.z = max(z_min, min(z_max, c.z))

            start_index = len(vertices)

            cols = BARK_PLATE_SUBDIV_ANGLE
            rows = BARK_PLATE_SUBDIV_Z

            random_raise = prng.uniform(0.0, BARK_PLATE_RANDOM_RAISE)

            # Additional per-plate sideways and vertical lift.
            plate_angle_shift = prng.uniform(
                -BARK_PLATE_RANDOM_TANGENT_SHIFT,
                BARK_PLATE_RANDOM_TANGENT_SHIFT
            )
            plate_z_shift = prng.uniform(
                -BARK_PLATE_RANDOM_Z_SHIFT,
                BARK_PLATE_RANDOM_Z_SHIFT
            )

            def bilerp_corner(u, v):
                """
                Bilinear interpolation in angle/z space.
                u = 0..1 across angle
                v = 0..1 along z
                """
                bottom = corners[0].lerp(corners[1], u)
                top = corners[3].lerp(corners[2], u)
                return bottom.lerp(top, v)

            # ------------------------------------------------
            # Create warped plate grid.
            # ------------------------------------------------

            for iz in range(rows + 1):
                v = iz / rows

                for ia in range(cols + 1):
                    u = ia / cols

                    az = bilerp_corner(u, v)

                    angle = az.x + plate_angle_shift
                    z = max(z_min, min(z_max, az.z + plate_z_shift))

                    # Make inner parts of plate more raised than edges.
                    middle_raise = (
                        math.sin(u * math.pi) *
                        math.sin(v * math.pi)
                    )

                    # Rough but deterministic per grid point.
                    point_noise = (
                        math.sin((u * 17.3 + v * 31.7 + prng.random()) * math.tau) *
                        0.5 + 0.5
                    )

                    rough = (
                        BARK_PLATE_INTERNAL_ROUGHNESS *
                        middle_raise *
                        point_noise
                    )

                    # Small edge curling: plate edges can lift/recess slightly.
                    edge_distance = min(u, 1.0 - u, v, 1.0 - v)
                    edge_curl = (0.5 - edge_distance) * 0.015 * prng.uniform(-1.0, 1.0)

                    inner_p = point_on_layer_boundary(
                        NUM_LAYERS,
                        angle,
                        z,
                        knots,
                        bark_extra=0.0
                    )

                    bump = 0.0
                    for knot in knots:
                        bump += knot.surface_bump * knot.influence(angle, z)

                    outer_p = point_on_layer_boundary(
                        NUM_LAYERS,
                        angle,
                        z,
                        knots,
                        bark_extra=(
                            BARK_THICKNESS
                            + bump
                            + random_raise
                            + rough
                            + edge_curl
                        )
                    )

                    vertices.append((outer_p.x, outer_p.y, outer_p.z))
                    vertices.append((inner_p.x, inner_p.y, inner_p.z))

            row_size = (cols + 1) * 2

            def outer_idx(iz, ia):
                return start_index + iz * row_size + ia * 2

            def inner_idx(iz, ia):
                return outer_idx(iz, ia) + 1

            # ------------------------------------------------
            # Outer plate surface.
            # ------------------------------------------------

            for iz in range(rows):
                for ia in range(cols):
                    a = outer_idx(iz, ia)
                    b = outer_idx(iz, ia + 1)
                    c = outer_idx(iz + 1, ia + 1)
                    d = outer_idx(iz + 1, ia)

                    faces.append((a, b, c, d))
                    face_materials.append("bark")

            # ------------------------------------------------
            # Side walls down to layer below.
            # These make the cracked plates look like broken chunks.
            # ------------------------------------------------

            # Left angular side
            for iz in range(rows):
                oa = outer_idx(iz, 0)
                ob = outer_idx(iz + 1, 0)
                ib = inner_idx(iz + 1, 0)
                iaa = inner_idx(iz, 0)

                faces.append((oa, ob, ib, iaa))
                face_materials.append("bark")

            # Right angular side
            for iz in range(rows):
                oa = outer_idx(iz, cols)
                ob = outer_idx(iz + 1, cols)
                ib = inner_idx(iz + 1, cols)
                iaa = inner_idx(iz, cols)

                faces.append((iaa, ib, ob, oa))
                face_materials.append("bark")

            # Bottom z side
            for ia in range(cols):
                oa = outer_idx(0, ia)
                ob = outer_idx(0, ia + 1)
                ib = inner_idx(0, ia + 1)
                iaa = inner_idx(0, ia)

                faces.append((iaa, ib, ob, oa))
                face_materials.append("bark")

            # Top z side
            for ia in range(cols):
                oa = outer_idx(rows, ia)
                ob = outer_idx(rows, ia + 1)
                ib = inner_idx(rows, ia + 1)
                iaa = inner_idx(rows, ia)

                faces.append((oa, ob, ib, iaa))
                face_materials.append("bark")

            # Bottom face against wood.
            for iz in range(rows):
                for ia in range(cols):
                    a = inner_idx(iz, ia)
                    b = inner_idx(iz + 1, ia)
                    c = inner_idx(iz + 1, ia + 1)
                    d = inner_idx(iz, ia + 1)

                    faces.append((a, b, c, d))
                    face_materials.append("bark")


# ============================================================
# PULLED-LAYER GRČA GEOMETRY
# ============================================================

def append_pulled_layer_knot(vertices, faces, face_materials, knot):
    """
    Creates a grča by pulling existing tree layers outward.

    The pulled layers use the same layer materials as the trunk.
    """

    center = centerline_at_z(knot.z)

    surface_normal = Vector((
        math.cos(knot.angle),
        math.sin(knot.angle),
        0.0
    )).normalized()

    base_radius = radius_at_z(knot.z)
    wood_radius = max(0.01, base_radius - BARK_THICKNESS)

    # Root starts at the chosen origin layer.
    origin_fraction = knot.origin_layer / NUM_LAYERS
    origin_radius = wood_radius * origin_fraction

    rx_origin, ry_origin = oval_radii(origin_radius)
    root_point = Vector((
        center.x + rx_origin * math.cos(knot.angle),
        center.y + ry_origin * math.sin(knot.angle),
        knot.z
    ))

    rx_surface, ry_surface = oval_radii(base_radius)
    surface_point = Vector((
        center.x + rx_surface * math.cos(knot.angle),
        center.y + ry_surface * math.sin(knot.angle),
        knot.z
    ))

    end = surface_point + knot.direction * knot.length_outside

    axis = end - root_point
    length = axis.length

    if length <= 0.0001:
        return

    direction = axis.normalized()
    u, v = make_basis_from_direction(direction)

    segments = 72
    length_segments = 18

    pulled_start = knot.origin_layer
    pulled_end = min(
        NUM_LAYERS - 1,
        knot.origin_layer + knot.pulled_layer_count - 1
    )

    for layer in range(pulled_start, pulled_end + 1):
        layer_start_index = len(vertices)

        local_layer_index = layer - pulled_start

        inner_frac = local_layer_index / knot.pulled_layer_count
        outer_frac = (local_layer_index + 1) / knot.pulled_layer_count

        inner_r_base = knot.radius * inner_frac
        outer_r_base = knot.radius * outer_frac

        if inner_r_base < 0.015:
            inner_r_base = 0.015

        material_name = material_for_layer(layer)

        for iz in range(length_segments + 1):
            t = iz / length_segments

            branch_center = root_point.lerp(end, t)

            # Slight taper outward.
            taper = 1.10 - 0.30 * t

            inner_r = inner_r_base * taper
            outer_r = outer_r_base * taper

            for ia in range(segments):
                angle = math.tau * ia / segments

                outer_p = (
                    branch_center +
                    u * (math.cos(angle) * outer_r) +
                    v * (math.sin(angle) * outer_r)
                )

                inner_p = (
                    branch_center +
                    u * (math.cos(angle) * inner_r) +
                    v * (math.sin(angle) * inner_r)
                )

                vertices.append((outer_p.x, outer_p.y, outer_p.z))
                vertices.append((inner_p.x, inner_p.y, inner_p.z))

        row_size = segments * 2

        for iz in range(length_segments):
            for ia in range(segments):
                outer_a = layer_start_index + iz * row_size + ia * 2
                inner_a = outer_a + 1

                outer_b = layer_start_index + iz * row_size + ((ia + 1) % segments) * 2
                inner_b = outer_b + 1

                outer_c = layer_start_index + (iz + 1) * row_size + ((ia + 1) % segments) * 2
                inner_c = outer_c + 1

                outer_d = layer_start_index + (iz + 1) * row_size + ia * 2
                inner_d = outer_d + 1

                faces.append((outer_a, outer_b, outer_c, outer_d))
                face_materials.append(material_name)

                faces.append((inner_b, inner_a, inner_d, inner_c))
                face_materials.append(material_name)

        # Outside cap for each pulled layer.
        cap_iz = length_segments

        for ia in range(segments):
            outer_a = layer_start_index + cap_iz * row_size + ia * 2
            inner_a = outer_a + 1

            outer_b = layer_start_index + cap_iz * row_size + ((ia + 1) % segments) * 2
            inner_b = outer_b + 1

            faces.append((inner_a, inner_b, outer_b, outer_a))
            face_materials.append(material_name)


# ============================================================
# FINAL MESH CREATION
# ============================================================

def create_layered_log_mesh():
    vertices = []
    faces = []
    face_materials = []

    # 1. Real wood layers.
    for layer in range(NUM_LAYERS):
        append_layer_shell(vertices, faces, face_materials, layer, KNOTS)

    # 2. Bark layer.
    append_bark_shell(vertices, faces, face_materials, KNOTS)

    # 3. Pulled-layer knots.
    for knot in KNOTS:
        append_pulled_layer_knot(vertices, faces, face_materials, knot)

    mesh = bpy.data.meshes.new("Layered procedural log mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()

    obj = bpy.data.objects.new("Layered log with pulled-layer grče", mesh)
    bpy.context.collection.objects.link(obj)

    add_materials_to_object(obj)
    lookup = material_lookup()

    for polygon, mat_name in zip(obj.data.polygons, face_materials):
        polygon.material_index = lookup[mat_name]

    return obj


log_obj = create_layered_log_mesh()


# ============================================================
# LIGHT AND CAMERA
# ============================================================

bpy.ops.object.light_add(type="AREA", location=(3, -4, 5))
light = bpy.context.object
light.name = "Large softbox light"
light.data.energy = 1000
light.data.size = 5

bpy.ops.object.camera_add(
    location=(7.2, -9.0, 3.6),
    rotation=(math.radians(63), 0, math.radians(42))
)
bpy.context.scene.camera = bpy.context.object


# ============================================================
# SET VIEW
# ============================================================

for obj in bpy.context.scene.objects:
    obj.select_set(False)

log_obj.select_set(True)
bpy.context.view_layer.objects.active = log_obj

print(f"Generated layered procedural log with {len(KNOTS)} grče.")
print(f"Number of wood layers: {NUM_LAYERS}")
print(f"Ovalnost: {OVALITY_PERCENT:.2f}%")
print(f"Koničnost: {TAPER_PERCENT:.2f}%")
print(f"Global krivost: {GLOBAL_CURVATURE_PERCENT:.2f}%")
print(f"Global bend count: {GLOBAL_BEND_COUNT}")

for i, knot in enumerate(KNOTS, start=1):
    print(f"Grča {i}:")
    print(f"  z: {knot.z:.2f}")
    print(f"  angle degrees: {math.degrees(knot.angle):.2f}")
    print(f"  origin layer: {knot.origin_layer}")
    print(f"  pulled layers: {knot.origin_layer} to {knot.origin_layer + knot.pulled_layer_count - 1}")
    print(f"  direction: {knot.direction}")