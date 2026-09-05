# Blender Plugin Toolkit

A small plugin toolkit for Blender, used to store those scattered little plugins. Install via remote library.

---

## Plugin 1: ENetSchematic — Same-Net Virtual Connection & Labeling

**Version:** 1.0  
**Blender:** 4.0 – 5.3  
**License:** GPL  
**Type:** Node Editor Add-on

### Overview

ENetSchematic brings circuit-schematic-style **net labels** to Blender's node editor.  
Using native **Reroute** nodes, you can assign a network name (e.g. `VCC`, `NET_CLK`).  
Nodes with the same net name are **automatically connected** via hidden real links — data flows between them, but the wires are invisible in the viewport.  
A bright yellow label is drawn next to each named Reroute, so you can instantly see logical connections without visual clutter.

### Features

- Assign custom net names to Reroute nodes
- Same‑net auto‑connection (real links, hidden from view)
- Visual net name labels (bright yellow, 13px, follows node)
- Right‑click context menu for quick editing
- N‑panel with scan, connect, disconnect and selection tools
- Net list with one‑click selection of all nodes in a net
- Safe cleanup on uninstall (auto‑links removed, no leftovers)

### Installation

1. Download `node_net_schematic_label.py`
2. In Blender: **Edit → Preferences → Add-ons → Install…**
3. Select the file and enable the add‑on (“Node: ENetSchematic”)
4. The add‑on works in any node editor (Shader, Geometry Nodes, Compositor, etc.)

### Usage

#### Assign a net name
- Select one or more Reroute nodes
- Right‑click → **Net Schematic → Set Net Name** (or use the N‑panel)
- Enter a net name (e.g. `NET_CLK`), click OK

#### Auto‑connect same nets
- In the N‑panel, press **Auto Connect Nets**  
  All Reroute nodes sharing the same non‑empty net name will be connected in a chain (first node is source). The connecting wires are real but invisible.

#### Scan & manage nets
- Press **Scan All Nets** to update the net list
- Each row shows net name and node count
- Click **Select** to select all Reroute nodes in that net

#### Clear a net name
- Select Reroute(s), right‑click → **Net Schematic → Clear Net Name**
- Or clear the name field in the N‑panel

#### Remove auto‑connections
- Press **Disconnect All Auto Links** in the N‑panel to remove all invisible links

### Notes

- Empty net names are ignored for both labeling and auto‑connection
- Auto‑links are stored as JSON in the node tree’s custom property `auto_net_links`
- Disabling or uninstalling the add‑on will automatically remove all auto‑links
- Manual user‑created links are never touched
- The hidden links are only invisible in the viewport; they are real links and can be inspected via Outliner (if enabled)

### Known Limitations

- No logical feedback (e.g. cycle prevention) beyond Blender’s own link restrictions
- Auto‑connection only works within the same node tree
- Labels are viewport‑only (not rendered in final output)

---

*This plugin is part of a toolkit – see the main repository for more small Blender add‑ons.*
