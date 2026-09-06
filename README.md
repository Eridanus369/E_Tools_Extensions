# Blender Plugin Toolkit

A small collection of Blender add-ons, installable via remote repository.

---

## Installation

### Method 1: Automatic Setup Script

1. Download the script: [add.py](https://github.com/Eridanus369/E_Tools_Extensions/blob/main/scripts/add.py)  
2. Open Blender’s **Scripting** workspace, paste or open the script and run it.  
3. The script will add the remote repository and sync automatically.  
4. Enable the add-on in **Preferences → Extensions**.

### Method 2: Manual Remote Repository

1. Go to **Edit → Preferences → Extensions**.  
2. Click **Add Remote Repository** and enter:  
   `https://eridanus369.github.io/E_Tools_Extensions/index.json`  
3. Click **Sync**, then find and enable the desired add-on.

---

## Plugins

<details>
<summary>1. ENetSchematic — Same-Net Virtual Connection & Labeling (v1.0)</summary>

Adds circuit-schematic style **net labels** to Blender’s node editor. Assign a net name to native Reroute nodes, and all nodes with the same net name are automatically connected with hidden real links. Labels are drawn next to each named Reroute.

**Compatible:** Blender 4.0 – 5.3  
**Type:** Node Editor Add-on  

<details>
<summary>Features</summary>

- Assign custom net names to Reroute nodes (e.g., `VCC`, `NET_CLK`)
- Same‑net nodes auto‑connect with real but invisible links
- Net name labels displayed next to nodes (color and size customizable in preferences)
- Right‑click context menu for quick editing
- N‑panel with scan, connect, disconnect, and selection tools
- Net list with one‑click selection of all nodes in a net
- Safe cleanup on uninstall (auto‑links removed, no leftovers)

</details>

<details>
<summary>Usage</summary>

- **Set net name**: Select Reroute node(s) → Right‑click → Net Schematic → Set Net Name
- **Auto connect**: In N‑panel, click **Auto Connect Nets**
- **Scan nets**: Click **Scan All Nets** to update the net list
- **Select net**: In the net list, click **Select** to select all nodes in that net
- **Clear net name**: Right‑click → Net Schematic → Clear Net Name
- **Remove auto links**: Click **Disconnect All Auto Links** in N‑panel

</details>

<details>
<summary>Notes & Limitations</summary>

- Empty net names are ignored
- Auto‑links are stored as JSON in the node tree’s custom property `auto_net_links`
- Disabling or uninstalling the add‑on removes all auto‑links automatically (manual links unaffected)
- Labels are viewport‑only and not rendered
- Auto‑connection works only within the same node tree

</details>

</details>
