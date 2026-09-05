bl_info = {
    "name": "ENetSchematic",
    "author": "Eridanus",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "Node Editor > N Panel > Net Schematic",
    "description": "Named nets over native Reroute nodes with auto-connect",
    "category": "Node",
}

import bpy
import blf
import gpu
import json
import math
import ctypes
from ctypes import c_float, c_char
from gpu_extras.batch import batch_for_shader

LABEL_COLOR = (0.9, 0.9, 0.2, 1.0)
LABEL_SIZE = 13
LABEL_OFFSET_Y = 10.0
FONT_ID = 0

_SOCKET_RUNTIME_LOCATION_OFFSET = 32 if bpy.app.version >= (5, 2, 0) else 24


class _BNodeSocketRuntime(ctypes.Structure):
    _fields_ = [
        ("_pad", c_char * _SOCKET_RUNTIME_LOCATION_OFFSET),
        ("location", c_float * 2),
    ]


class _BNodeSocket(ctypes.Structure):
    _fields_ = [
        ("_pad", c_char * 456),
        ("runtime", ctypes.POINTER(_BNodeSocketRuntime)),
    ]


def _get_socket_view_loc(socket):
    try:
        bs = _BNodeSocket.from_address(socket.as_pointer())
        loc = bs.runtime.contents.location
        return (loc[0], loc[1])
    except Exception:
        return None


def _dpi_fac():
    return bpy.context.preferences.system.dpi / 72

_handlers = []
_keymap_items = []
_timer_handle = None


def get_net_map(node_tree):
    try:
        return json.loads(node_tree.get("net_map", "{}"))
    except Exception:
        return {}


def save_net_map(node_tree, data):
    node_tree["net_map"] = json.dumps(data)


def get_auto_links(node_tree):
    try:
        return json.loads(node_tree.get("auto_net_links", "[]"))
    except Exception:
        return []


def save_auto_links(node_tree, links):
    node_tree["auto_net_links"] = json.dumps(links)


def _get_node_tree(context):
    space = getattr(context, "space_data", None)
    if space is None or space.type != "NODE_EDITOR":
        return None
    return getattr(space, "edit_tree", None) or getattr(space, "node_tree", None)


def _selected_reroutes(context):
    nt = _get_node_tree(context)
    if not nt:
        return []
    return [n for n in nt.nodes if n.select and n.type == "REROUTE"]


def _active_reroute(context):
    nt = _get_node_tree(context)
    if not nt:
        return None
    active = getattr(nt.nodes, "active", None)
    if active is not None and active.type == "REROUTE":
        return active
    for n in nt.nodes:
        if n.select and n.type == "REROUTE":
            return n
    return None


def _reroute_at_cursor(context, event):
    nt = _get_node_tree(context)
    region = getattr(context, "region", None)
    if not nt or region is None:
        return None
    mx = getattr(event, "mouse_region_x", None)
    my = getattr(event, "mouse_region_y", None)
    if mx is None or my is None:
        return None
    best = None
    best_dist = 14.0 * 14.0
    for n in nt.nodes:
        if n.type != "REROUTE":
            continue
        p = region.view2d.view_to_region(n.location.x, n.location.y, clip=False)
        dx = p[0] - mx
        dy = p[1] - my
        d = dx * dx + dy * dy
        if d < best_dist:
            best_dist = d
            best = n
    return best


def _creation_order(node_tree):
    return {n: i for i, n in enumerate(node_tree.nodes)}


def disconnect_auto_links(node_tree):
    auto_links = get_auto_links(node_tree)
    recorded = set()
    for rec in auto_links:
        if len(rec) >= 4:
            recorded.add((rec[0], rec[2]))
    for link in list(node_tree.links):
        if link.from_node is None or link.to_node is None:
            continue
        if (link.from_node.name, link.to_node.name) in recorded:
            try:
                node_tree.links.remove(link)
            except Exception:
                pass
    save_auto_links(node_tree, [])


def _link_exists(a, b):
    if a.outputs:
        for lk in a.outputs[0].links:
            if lk.to_node == b:
                return True
    if b.outputs:
        for lk in b.outputs[0].links:
            if lk.to_node == a:
                return True
    return False


def _would_cycle(a, b):
    stack = [b]
    seen = set()
    while stack:
        cur = stack.pop()
        if cur == a:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        if not cur.outputs:
            continue
        for lk in cur.outputs[0].links:
            if lk.to_node is not None:
                stack.append(lk.to_node)
    return False


def auto_connect_nets(node_tree):
    disconnect_auto_links(node_tree)
    order = _creation_order(node_tree)
    groups = {}
    for node in node_tree.nodes:
        if node.type == "REROUTE":
            name = node.get("net_name", "")
            if name:
                groups.setdefault(name, []).append(node)
    auto_links = []
    for name, nodes in groups.items():
        nodes.sort(key=lambda n: order[n])
        for i in range(len(nodes) - 1):
            a = nodes[i]
            b = nodes[i + 1]
            out = a.outputs[0]
            inp = b.inputs[0]
            if inp.is_linked:
                continue
            if _link_exists(a, b):
                continue
            if _would_cycle(a, b):
                continue
            try:
                link = node_tree.links.new(out, inp)
                if link is not None:
                    auto_links.append([a.name, 0, b.name, 0])
            except Exception:
                continue
    save_auto_links(node_tree, auto_links)
    return len(auto_links)


def scan_nets(node_tree):
    order = _creation_order(node_tree)
    net_map = {}
    for node in node_tree.nodes:
        if node.type == "REROUTE":
            name = node.get("net_name", "")
            if name:
                net_map.setdefault(name, []).append(node)
    result = {}
    for name, nodes in net_map.items():
        nodes.sort(key=lambda n: order[n])
        result[name] = [n.name for n in nodes]
    save_net_map(node_tree, result)
    return result


def _view_to_region_float(region, x, y):
    v2d = region.view2d
    vx0, vy0 = v2d.region_to_view(0.0, 0.0)
    vx1, vy1 = v2d.region_to_view(1.0, 1.0)
    sx = 0.0 if vx1 == vx0 else 1.0 / (vx1 - vx0)
    sy = 0.0 if vy1 == vy0 else 1.0 / (vy1 - vy0)
    return ((x - vx0) * sx, (y - vy0) * sy)


def _background_color():
    try:
        bg = bpy.context.preferences.themes[0].node_editor.space.back
        return (bg[0], bg[1], bg[2], 1.0)
    except Exception:
        return (0.125, 0.125, 0.125, 1.0)


def _prefs():
    addon = bpy.context.preferences.addons.get("ENetSchematic")
    return getattr(addon, "preferences", None)


def _curving_factor():
    try:
        return bpy.context.preferences.themes[0].node_editor.noodle_curving / 10.0
    except Exception:
        return 0.5


def _handle_offset(x1, y1, x2, y2, curv):
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    slope = 0.0 if dx == 0 else dy / dx
    raw_curving = curv * 10.0
    clamp_factor = min(1.0, slope * (4.5 - 0.25 * raw_curving))
    return curv * dx * clamp_factor


def _erase_geometry():
    fac = _dpi_fac()
    ps = bpy.context.preferences.system.pixel_size
    widget_unit = round(18 * fac) + 2 * ps
    width = widget_unit * 0.6
    extend_px = widget_unit * 0.4
    return width, extend_px


def _bezier_points(region, p0, p1, steps=28, extend_px=0.0):
    curv = _curving_factor()
    dx = p1[0] - p0[0]
    if curv <= 0.001:
        off = abs(dx) / 3.0
    else:
        off = _handle_offset(p0[0], p0[1], p1[0], p1[1], curv)
    r0 = _view_to_region_float(region, p0[0], p0[1])
    r1 = _view_to_region_float(region, p0[0] + off, p0[1])
    r2 = _view_to_region_float(region, p1[0] - off, p1[1])
    r3 = _view_to_region_float(region, p1[0], p1[1])
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = mt * mt * mt * r0[0] + 3 * mt * mt * t * r1[0] + 3 * mt * t * t * r2[0] + t * t * t * r3[0]
        y = mt * mt * mt * r0[1] + 3 * mt * mt * t * r1[1] + 3 * mt * t * t * r2[1] + t * t * t * r3[1]
        pts.append((x, y))
    if extend_px > 0.0 and len(pts) >= 2:
        s0x, s0y = pts[0]
        s1x, s1y = pts[1]
        sdx, sdy = s0x - s1x, s0y - s1y
        sl = math.hypot(sdx, sdy)
        if sl > 1e-6:
            pts[0] = (s0x + sdx / sl * extend_px, s0y + sdy / sl * extend_px)
        e0x, e0y = pts[-1]
        e1x, e1y = pts[-2]
        edx, edy = e0x - e1x, e0y - e1y
        el = math.hypot(edx, edy)
        if el > 1e-6:
            pts[-1] = (e0x + edx / el * extend_px, e0y + edy / el * extend_px)
    return pts


def _ribbon(points, width):
    verts = []
    indices = []
    half = width * 0.5
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        dx = x1 - x0
        dy = y1 - y0
        length = math.hypot(dx, dy)
        if length < 1e-6:
            continue
        nx = -dy / length * half
        ny = dx / length * half
        base = len(verts)
        verts.extend([
            (x0 + nx, y0 + ny),
            (x0 - nx, y0 - ny),
            (x1 + nx, y1 + ny),
            (x1 - nx, y1 - ny),
        ])
        indices.extend([(base, base + 1, base + 2), (base + 1, base + 3, base + 2)])
    return verts, indices


def _draw_erase():
    context = bpy.context
    space = context.space_data
    region = context.region
    nt = _get_node_tree(context)
    if not nt or space.type != "NODE_EDITOR":
        return
    auto_links = get_auto_links(nt)
    if not auto_links:
        return
    recorded = set()
    for rec in auto_links:
        if len(rec) >= 4:
            recorded.add((rec[0], rec[2]))
    bg = _background_color()
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    gpu.state.blend_set("ALPHA")
    for link in nt.links:
        if link.from_node is None or link.to_node is None:
            continue
        if (link.from_node.name, link.to_node.name) not in recorded:
            continue
        pa = _get_socket_view_loc(link.from_socket)
        pb = _get_socket_view_loc(link.to_socket)
        if pa is None:
            nloc = link.from_node.location
            fac = _dpi_fac()
            pa = (nloc.x * fac, nloc.y * fac)
        if pb is None:
            nloc = link.to_node.location
            fac = _dpi_fac()
            pb = (nloc.x * fac, nloc.y * fac)
        erase_width, extend_px = _erase_geometry()
        curve = _bezier_points(region, pa, pb, extend_px=extend_px)
        if len(curve) < 2:
            continue
        verts, indices = _ribbon(curve, erase_width)
        if not verts:
            continue
        batch = batch_for_shader(shader, "TRIS", {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", bg)
        batch.draw(shader)
    gpu.state.blend_set("NONE")


def _draw_labels():
    context = bpy.context
    space = context.space_data
    region = context.region
    nt = _get_node_tree(context)
    if not nt or space.type != "NODE_EDITOR":
        return
    prefs = _prefs()
    size = prefs.label_size if prefs is not None else LABEL_SIZE
    rgb = prefs.label_color if prefs is not None else LABEL_COLOR[:3]
    blf.size(FONT_ID, size)
    blf.color(FONT_ID, rgb[0], rgb[1], rgb[2], 1.0)
    for node in nt.nodes:
        if node.type != "REROUTE":
            continue
        name = node.get("net_name", "")
        if not name:
            continue
        loc = _get_socket_view_loc(node.outputs[0]) if node.outputs else None
        if loc is None:
            fac = _dpi_fac()
            loc = (node.location.x * fac, node.location.y * fac)
        sx, sy = _view_to_region_float(region, loc[0], loc[1])
        w, _ = blf.dimensions(FONT_ID, name)
        blf.position(FONT_ID, sx - w * 0.5, sy + LABEL_OFFSET_Y, 0)
        blf.draw(FONT_ID, name)


def draw_callback():
    _draw_erase()
    _draw_labels()


def _sync_handlers():
    active = []
    try:
        for wm in bpy.data.window_managers:
            for win in wm.windows:
                for area in win.screen.areas:
                    if area.type != "NODE_EDITOR":
                        continue
                    space = area.spaces.active
                    active.append(space)
                    if not any(s == space for s, _ in _handlers):
                        try:
                            h = space.draw_handler_add(draw_callback, (), "WINDOW", "POST_PIXEL")
                            _handlers.append((space, h))
                        except Exception:
                            pass
    except Exception:
        return
    for space, h in list(_handlers):
        if space not in active:
            try:
                space.draw_handler_remove(h, "WINDOW")
            except Exception:
                pass
            _handlers.remove((space, h))


def _sync_timer():
    _sync_handlers()
    return 0.5


def unregister_handlers():
    for space, h in _handlers:
        try:
            space.draw_handler_remove(h, "WINDOW")
        except Exception:
            pass
    _handlers.clear()


def _all_node_trees():
    seen = set()
    trees = []
    for obj in list(bpy.data.materials) + list(bpy.data.worlds) + list(bpy.data.scenes):
        try:
            nt = obj.node_tree
        except Exception:
            nt = None
        if nt is not None and nt not in seen:
            seen.add(nt)
            trees.append(nt)
    for ng in bpy.data.node_groups:
        if ng not in seen:
            seen.add(ng)
            trees.append(ng)
    return trees


def cleanup_all_trees():
    for nt in _all_node_trees():
        try:
            disconnect_auto_links(nt)
            if "auto_net_links" in nt:
                del nt["auto_net_links"]
            if "net_map" in nt:
                del nt["net_map"]
        except Exception:
            pass


class NODE_NET_OT_set_net_name(bpy.types.Operator):
    bl_idname = "node_net.set_net_name"
    bl_label = "Set Net Name"
    bl_description = "Assign a net name to selected Reroute nodes"
    bl_options = {"REGISTER", "UNDO"}

    net_name: bpy.props.StringProperty(name="Net Name", default="NET_")

    @classmethod
    def poll(cls, context):
        return bool(_selected_reroutes(context))

    def invoke(self, context, event):
        nodes = _selected_reroutes(context)
        if not nodes:
            self.report({"WARNING"}, "No Reroute node selected")
            return {"CANCELLED"}
        if len(nodes) == 1:
            self.net_name = nodes[0].get("net_name", "") or "NET_"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        nodes = _selected_reroutes(context)
        if not nodes:
            self.report({"WARNING"}, "No Reroute node selected")
            return {"CANCELLED"}
        for node in nodes:
            node["net_name"] = self.net_name
        nt = _get_node_tree(context)
        if nt:
            scan_nets(nt)
            auto_connect_nets(nt)
        return {"FINISHED"}


class NODE_NET_OT_clear_net_name(bpy.types.Operator):
    bl_idname = "node_net.clear_net_name"
    bl_label = "Clear Net Name"
    bl_description = "Remove the net name from selected Reroute nodes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(_selected_reroutes(context))

    def execute(self, context):
        nodes = _selected_reroutes(context)
        if not nodes:
            self.report({"WARNING"}, "No Reroute node selected")
            return {"CANCELLED"}
        for node in nodes:
            node["net_name"] = ""
        nt = _get_node_tree(context)
        if nt:
            scan_nets(nt)
            auto_connect_nets(nt)
        return {"FINISHED"}


class NODE_NET_OT_scan_nets(bpy.types.Operator):
    bl_idname = "node_net.scan_nets"
    bl_label = "Scan All Nets"
    bl_description = "Scan Reroute nets and refresh the net list"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _get_node_tree(context) is not None

    def execute(self, context):
        nt = _get_node_tree(context)
        if not nt:
            self.report({"WARNING"}, "No node tree found")
            return {"CANCELLED"}
        result = scan_nets(nt)
        auto_connect_nets(nt)
        self.report({"INFO"}, "Found %d net(s)" % len(result))
        return {"FINISHED"}


class NODE_NET_OT_auto_connect(bpy.types.Operator):
    bl_idname = "node_net.auto_connect"
    bl_label = "Auto Connect Nets"
    bl_description = "Chain-connect Reroute nodes sharing the same net name"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _get_node_tree(context) is not None

    def execute(self, context):
        nt = _get_node_tree(context)
        if not nt:
            self.report({"WARNING"}, "No node tree found")
            return {"CANCELLED"}
        scan_nets(nt)
        count = auto_connect_nets(nt)
        self.report({"INFO"}, "Created %d auto link(s)" % count)
        return {"FINISHED"}


class NODE_NET_OT_disconnect_auto(bpy.types.Operator):
    bl_idname = "node_net.disconnect_auto"
    bl_label = "Disconnect All Auto Links"
    bl_description = "Remove all automatically created links in this node tree"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _get_node_tree(context) is not None

    def execute(self, context):
        nt = _get_node_tree(context)
        if not nt:
            self.report({"WARNING"}, "No node tree found")
            return {"CANCELLED"}
        disconnect_auto_links(nt)
        return {"FINISHED"}


class NODE_NET_OT_select_net(bpy.types.Operator):
    bl_idname = "node_net.select_net"
    bl_label = "Select Net"
    bl_description = "Select all Reroute nodes belonging to this net"
    bl_options = {"REGISTER", "UNDO"}

    net_name: bpy.props.StringProperty(name="Net Name")

    @classmethod
    def poll(cls, context):
        return _get_node_tree(context) is not None

    def execute(self, context):
        nt = _get_node_tree(context)
        if not nt:
            self.report({"WARNING"}, "No node tree found")
            return {"CANCELLED"}
        matches = [n for n in nt.nodes if n.type == "REROUTE" and n.get("net_name", "") == self.net_name]
        if not matches:
            self.report({"WARNING"}, "No nodes found for net")
            return {"CANCELLED"}
        for n in nt.nodes:
            n.select = False
        for n in matches:
            n.select = True
        nt.nodes.active = matches[0]
        return {"FINISHED"}


class NODE_NET_OT_reroute_dblclick(bpy.types.Operator):
    bl_idname = "node_net.reroute_dblclick"
    bl_label = "Edit Reroute Net Name"
    bl_description = "Quickly edit the net name of the Reroute node under the cursor"
    bl_options = {"REGISTER", "INTERNAL"}

    @classmethod
    def poll(cls, context):
        return _get_node_tree(context) is not None

    def invoke(self, context, event):
        node = _reroute_at_cursor(context, event)
        if node is None:
            node = _active_reroute(context)
        if node is None:
            return {"PASS_THROUGH"}
        nt = _get_node_tree(context)
        if nt is not None:
            for n in nt.nodes:
                if n.type == "REROUTE":
                    n.select = False
            node.select = True
            nt.nodes.active = node
        bpy.ops.node_net.set_net_name("INVOKE_DEFAULT")
        return {"FINISHED"}


class NODE_NET_MT_context_menu(bpy.types.Menu):
    bl_idname = "NODE_NET_MT_context_menu"
    bl_label = "Net Schematic"

    def draw(self, context):
        layout = self.layout
        layout.operator("node_net.set_net_name", text="Set Net Name")
        layout.operator("node_net.clear_net_name", text="Clear Net Name")
        layout.separator()
        layout.operator("node_net.auto_connect", text="Auto Connect Nets")


def context_menu_draw(self, context):
    if _selected_reroutes(context):
        self.layout.menu("NODE_NET_MT_context_menu", text="Net Schematic")


class NODE_NET_PT_main_panel(bpy.types.Panel):
    bl_idname = "NODE_NET_PT_main_panel"
    bl_label = "Net Schematic"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Net Schematic"

    def draw(self, context):
        layout = self.layout
        active = _active_reroute(context)
        if active is not None and "net_name" in active:
            layout.prop(active, '["net_name"]', text="Net Name")
        elif active is not None:
            layout.label(text="No net name set", icon="INFO")
        else:
            layout.label(text="Select a Reroute node", icon="INFO")
        if active is not None:
            layout.operator("node_net.set_net_name", text="Edit Net Label Dialog", icon="GREASEPENCIL")
            layout.operator("node_net.clear_net_name", text="Clear Net Name", icon="X")
        layout.separator()
        layout.operator("node_net.scan_nets", text="Scan All Nets", icon="FILE_REFRESH")
        layout.operator("node_net.auto_connect", text="Auto Connect Nets", icon="LINKED")
        layout.operator("node_net.disconnect_auto", text="Disconnect All Auto Links", icon="UNLINKED")


class NODE_NET_PT_net_list_panel(bpy.types.Panel):
    bl_idname = "NODE_NET_PT_net_list_panel"
    bl_label = "Net List"
    bl_parent_id = "NODE_NET_PT_main_panel"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Net Schematic"

    def draw(self, context):
        layout = self.layout
        nt = _get_node_tree(context)
        if not nt:
            layout.label(text="No node tree", icon="INFO")
            return
        net_map = get_net_map(nt)
        if not net_map:
            layout.label(text="No nets found", icon="INFO")
            return
        for name in sorted(net_map.keys()):
            node_names = net_map[name]
            row = layout.row(align=True)
            row.label(text="%s  (%d)" % (name, len(node_names)))
            prop = row.operator("node_net.select_net", text="Select")
            prop.net_name = name


class ENetSchematicPreferences(bpy.types.AddonPreferences):
    bl_idname = "ENetSchematic"

    label_color: bpy.props.FloatVectorProperty(
        name="Label Color",
        subtype="COLOR",
        size=3,
        default=(0.9, 0.9, 0.2),
        min=0.0,
        max=1.0,
    )
    label_size: bpy.props.IntProperty(
        name="Label Size",
        default=13,
        min=8,
        max=64,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "label_color")
        layout.prop(self, "label_size")


classes = (
    NODE_NET_OT_set_net_name,
    NODE_NET_OT_clear_net_name,
    NODE_NET_OT_scan_nets,
    NODE_NET_OT_auto_connect,
    NODE_NET_OT_disconnect_auto,
    NODE_NET_OT_select_net,
    NODE_NET_OT_reroute_dblclick,
    NODE_NET_MT_context_menu,
    NODE_NET_PT_main_panel,
    NODE_NET_PT_net_list_panel,
    ENetSchematicPreferences,
)


def register_keymap():
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon
        if kc:
            km = kc.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
            kmi = km.keymap_items.new("node_net.reroute_dblclick", type="LEFTMOUSE", value="DOUBLE_CLICK")
            _keymap_items.append((km, kmi))
    except Exception:
        pass


def unregister_keymap():
    for km, kmi in _keymap_items:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymap_items.clear()


def _load_post(_):
    _sync_handlers()


def register():
    global _timer_handle
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_context_menu.append(context_menu_draw)
    bpy.app.handlers.load_post.append(_load_post)
    register_keymap()
    try:
        _timer_handle = bpy.app.timers.register(_sync_timer, first_interval=0.0, persistent=True)
    except Exception:
        _timer_handle = None


def unregister():
    global _timer_handle
    unregister_keymap()
    if _timer_handle is not None:
        try:
            bpy.app.timers.unregister(_timer_handle)
        except Exception:
            pass
        _timer_handle = None
    try:
        bpy.app.handlers.load_post.remove(_load_post)
    except Exception:
        pass
    try:
        bpy.types.NODE_MT_context_menu.remove(context_menu_draw)
    except Exception:
        pass
    unregister_handlers()
    try:
        cleanup_all_trees()
    except Exception:
        pass
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()