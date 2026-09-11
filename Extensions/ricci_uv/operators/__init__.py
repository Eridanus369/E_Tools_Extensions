import bpy
from .op_unwrap import RICCI_OT_unwrap
from .op_curvature_preview import (
    RICCI_OT_curvature_preview,
    RICCI_OT_curvature_export,
)
from .op_decay_holonomy import RICCI_OT_decay_holonomy
from .op_optimize_topology import RICCI_OT_optimize_topology
from .op_cone_overlay import (
    RICCI_OT_cone_overlay,
    RICCI_OT_cone_overlay_clear,
)
from .op_smooth_cone_uv import RICCI_OT_smooth_cone_uv


_classes = [
    RICCI_OT_unwrap,
    RICCI_OT_curvature_preview,
    RICCI_OT_curvature_export,
    RICCI_OT_decay_holonomy,
    RICCI_OT_optimize_topology,
    RICCI_OT_cone_overlay,
    RICCI_OT_cone_overlay_clear,
    RICCI_OT_smooth_cone_uv,
]


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)