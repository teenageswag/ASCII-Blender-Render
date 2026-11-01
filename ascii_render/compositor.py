"""Native compositor graph, evaluated identically by CPU and GPU compositors."""

import bpy

from .glyphs import atlas_for, character_ramp
from . import smart

OWNER = 'ascii_render_owned'
SCHEMA = 6

# All changing numbers are group inputs driven from the owning Scene. This keeps
# animation in Blender's dependency graph; there are no per-frame Python hooks.
CONTROLS = (
    ('Columns', 'NodeSocketFloat', 'columns', 'value'),
    ('Cell Aspect', 'NodeSocketFloat', 'cell_aspect', 'value'),
    ('Glyph Scale', 'NodeSocketFloat', 'glyph_scale', 'value'),
    ('Exposure', 'NodeSocketFloat', 'exposure', 'value'),
    ('Contrast', 'NodeSocketFloat', 'contrast', 'value'),
    ('Gamma', 'NodeSocketFloat', 'gamma', 'value'),
    ('Invert', 'NodeSocketFloat', 'invert', 'value'),
    ('Color Mode', 'NodeSocketFloat', 'color_mode', 'value'),
    ('Color Gain', 'NodeSocketFloat', 'color_gain', 'value'),
    ('Foreground', 'NodeSocketColor', 'foreground', 'value'),
    ('Background', 'NodeSocketColor', 'background', 'value'),
    ('Contours', 'NodeSocketFloat', 'contours', 'value'),
    ('Edge Threshold', 'NodeSocketFloat', 'edge_threshold', 'value'),
    ('Transparent', 'NodeSocketFloat', 'transparent_background', 'value'),
    ('Strength', 'NodeSocketFloat', 'strength', 'value'),
    ('Enabled', 'NodeSocketFloat', 'enabled', 'value'),
    ('World Mode', 'NodeSocketFloat', 'world_mode', 'value'),
    ('Match Mode', 'NodeSocketBool', 'match_mode', 'value'),
    ('Adaptive Strength', 'NodeSocketFloat', 'adaptive_strength', 'value'),
    ('Adaptive Floor', 'NodeSocketFloat', 'adaptive_floor', 'value'),
    ('Shape Strength', 'NodeSocketFloat', 'shape_strength', 'value'),
    ('Min Scale', 'NodeSocketFloat', 'min_scale', 'value'),
    ('Max Scale', 'NodeSocketFloat', 'max_scale', 'value'),
    ('Scale Strength', 'NodeSocketFloat', 'scale_strength', 'value'),
    ('Saturation', 'NodeSocketFloat', 'saturation', 'value'),
    ('Minimum Contrast', 'NodeSocketFloat', 'min_contrast', 'value'),
    ('Remove Original Edge', 'NodeSocketFloat', 'remove_original_edge', 'value'),
    ('Edge Coverage Threshold', 'NodeSocketFloat', 'edge_mask_threshold', 'value'),
    ('Grid Mode', 'NodeSocketFloat', 'grid_mode', 'value'),
    ('Cell Pixels', 'NodeSocketFloat', 'cell_pixels', 'value'),
)


class Graph:
    def __init__(self, tree):
        self.tree = tree
        self.count = 0

    def node(self, kind, label):
        node = self.tree.nodes.new(kind)
        node.label = label
        node.name = label
        node.location = ((self.count % 10) * 200, -(self.count // 10) * 190)
        self.count += 1
        return node

    def put(self, socket, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, socket)
        else:
            socket.default_value = value

    def math(self, operation, a, b=None, label=None, clamp=False):
        node = self.node('ShaderNodeMath', label or operation.title())
        node.operation = operation
        node.use_clamp = clamp
        self.put(node.inputs[0], a)
        if b is not None:
            self.put(node.inputs[1], b)
        return node.outputs[0]

    def xyz(self, x, y, z=1.0, label='UV coordinates'):
        node = self.node('ShaderNodeCombineXYZ', label)
        for socket, value in zip(node.inputs, (x, y, z)):
            self.put(socket, value)
        return node.outputs[0]

    def separate(self, vector, label):
        node = self.node('ShaderNodeSeparateXYZ', label)
        self.put(node.inputs[0], vector)
        return node.outputs

    def mix(self, factor, a, b, color=False, label='Mix'):
        node = self.node('ShaderNodeMix', label)
        node.data_type = 'RGBA' if color else 'FLOAT'
        node.clamp_factor = True
        self.put(node.inputs[0], factor)
        self.put(node.inputs[6 if color else 2], a)
        self.put(node.inputs[7 if color else 3], b)
        return node.outputs[2 if color else 0]

    def sample(self, image, u, v, label, nearest=False):
        node = self.node('CompositorNodeMapUV', label)
        node.inputs['Interpolation'].default_value = 'Nearest' if nearest else 'Bilinear'
        node.inputs['Extension X'].default_value = 'Extend'
        node.inputs['Extension Y'].default_value = 'Extend'
        self.put(node.inputs['Image'], image)
        self.put(node.inputs['UV'], self.xyz(u, v, label=label + ' UV'))
        return node.outputs[0]

    def switch(self, condition, off, on, label, color=False):
        # 5.2 static lazy evaluation requires a BOOLEAN Group Input connected
        # directly to the modern Switch. Float-to-bool conversion defeats it.
        node = self.node('GeometryNodeSwitch', label)
        node.input_type = 'RGBA' if color else 'FLOAT'
        self.put(node.inputs['Switch'], condition)
        self.put(node.inputs['False'], off)
        self.put(node.inputs['True'], on)
        return node.outputs[0]

    def luminance(self, image, label):
        node = self.node('CompositorNodeRGBToBW', label)
        self.put(node.inputs[0], image)
        return node.outputs[0]


def build_effect(settings):
    tree = bpy.data.node_groups.new('ASCII Render • Effect', 'CompositorNodeTree')
    tree[OWNER] = True
    tree['ascii_schema'] = SCHEMA
    tree.interface.new_socket(name='Image', in_out='INPUT', socket_type='NodeSocketColor')
    for name, socket_type, _, _ in CONTROLS:
        tree.interface.new_socket(name=name, in_out='INPUT', socket_type=socket_type)
    tree.interface.new_socket(name='Object Mask', in_out='INPUT', socket_type='NodeSocketColor')
    tree.interface.new_socket(name='Use Object Mask', in_out='INPUT', socket_type='NodeSocketFloat')
    tree.interface.new_socket(name='Albedo', in_out='INPUT', socket_type='NodeSocketColor')
    tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    g = Graph(tree)
    inputs = g.node('NodeGroupInput', 'Settings').outputs
    original = inputs['Image']
    info = g.node('CompositorNodeImageInfo', 'Image size')
    g.put(info.inputs[0], original)
    dimensions = g.separate(info.outputs['Dimensions'], 'Image dimensions')
    coords = g.node('CompositorNodeImageCoordinates', 'Image coordinates')
    g.put(coords.inputs[0], original)
    uv = g.separate(coords.outputs['Normalized'], 'Normalized coordinates')
    columns = g.mix(inputs['Grid Mode'], inputs['Columns'],
                    g.math('DIVIDE', dimensions[0], inputs['Cell Pixels']))
    columns = g.math('MAXIMUM', g.switch(inputs['Match Mode'], columns,
        g.math('MINIMUM', columns, g.math('DIVIDE', dimensions[0], 8)), 'Smart minimum cell size'), 1,
        label='Effective columns')
    rows = g.math('MAXIMUM', g.math('ROUND', g.math('DIVIDE',
        g.math('MULTIPLY', columns, g.math('DIVIDE', dimensions[1], dimensions[0])), inputs['Cell Aspect'])), 1)
    gx, gy = g.math('MULTIPLY', uv[0], columns), g.math('MULTIPLY', uv[1], rows)
    center_u = g.math('DIVIDE', g.math('ADD', g.math('FLOOR', gx), 0.5), columns)
    center_v = g.math('DIVIDE', g.math('ADD', g.math('FLOOR', gy), 0.5), rows)
    local_u, local_v = g.math('FRACT', gx), g.math('FRACT', gy)

    # Average over most of a cell before sampling. This reduces sparkle on fine
    # textures in animation while keeping the spatial grid stable.
    blur = g.node('CompositorNodeBlur', 'Cell averaging')
    blur.inputs['Type'].default_value = 'Gaussian'
    g.put(blur.inputs['Image'], original)
    g.put(blur.inputs['Size'], g.xyz(
        g.math('MULTIPLY', g.math('DIVIDE', dimensions[0], columns), 0.45),
        g.math('MULTIPLY', g.math('DIVIDE', dimensions[1], rows), 0.45), 0, 'Cell averaging radius'))
    sampled = g.sample(blur.outputs[0], center_u, center_v, 'Cell color')
    lum = g.luminance(sampled, 'Cell luminance')
    exposed = g.math('MULTIPLY', lum, g.math('POWER', 2, inputs['Exposure']))
    perceptual = g.math('POWER', g.math('MAXIMUM', exposed, 0), 1 / 2.2)
    contrast = g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', perceptual, 0.5), inputs['Contrast']), 0.5, clamp=True)
    tone = g.math('POWER', contrast, g.math('DIVIDE', 1, inputs['Gamma']), clamp=True)
    tone = g.mix(inputs['Invert'], tone, g.math('SUBTRACT', 1, tone), label='Invert density')
    ramp = character_ramp(settings)
    index = g.math('MINIMUM', g.math('FLOOR', g.math('MULTIPLY', tone, len(ramp), label='Fill glyph index')), len(ramp) - 1, label='Last fill index')
    atlas_image = atlas_for(ramp)
    smart_tone, pattern, smart_dx, smart_dy = smart.analyze(
        g, inputs, original, dimensions, columns, rows, center_u, center_v)
    smart_index = smart.match(g, inputs, smart_tone, pattern, ramp, atlas_image)
    index = g.switch(inputs['Match Mode'], index, smart_index, 'Classic or Smart matching')

    # Central differences at cell boundaries give a gradient shared by the whole
    # cell. Its perpendicular selects -, |, / or \\ as the contour tangent.
    du, dv = g.math('DIVIDE', 0.5, columns), g.math('DIVIDE', 0.5, rows)
    neighbors = []
    for label, u, v in (
        ('Left', g.math('SUBTRACT', center_u, du), center_v),
        ('Right', g.math('ADD', center_u, du), center_v),
        ('Down', center_u, g.math('SUBTRACT', center_v, dv)),
        ('Up', center_u, g.math('ADD', center_v, dv)),
    ):
        value = g.luminance(g.sample(blur.outputs[0], u, v, label + ' neighbor'), label + ' luminance')
        neighbors.append(g.math('POWER', g.math('MAXIMUM', value, 0), 1 / 2.2))
    dx = g.math('SUBTRACT', neighbors[1], neighbors[0])
    dy = g.math('SUBTRACT', neighbors[3], neighbors[2])
    dx = g.switch(inputs['Match Mode'], dx, smart_dx, 'Classic or Smart gradient X')
    dy = g.switch(inputs['Match Mode'], dy, smart_dy, 'Classic or Smart gradient Y')
    ax, ay = g.math('ABSOLUTE', dx), g.math('ABSOLUTE', dy)
    magnitude = g.math('SQRT', g.math('ADD', g.math('MULTIPLY', dx, dx), g.math('MULTIPLY', dy, dy)))
    diagonal = g.mix(g.math('GREATER_THAN', g.math('MULTIPLY', dx, dy), 0), 2, 3)
    edge_index = g.mix(g.math('GREATER_THAN', ax, g.math('MULTIPLY', ay, 2.414214)), diagonal, 1)
    edge_index = g.mix(g.math('GREATER_THAN', ay, g.math('MULTIPLY', ax, 2.414214)), edge_index, 0)
    edge_index = g.math('ADD', edge_index, len(ramp), label='Contour atlas offset')
    edge_gate = g.math('MULTIPLY', inputs['Contours'], g.math('GREATER_THAN', magnitude, inputs['Edge Threshold']))
    index = g.mix(edge_gate, index, edge_index, label='Fill or contour')

    # Scaling local UVs changes ink size without changing grid spacing. Explicit
    # bounds prevent neighboring atlas glyphs leaking when scale is below one.
    importance = g.math('MAXIMUM', smart_tone, g.math('MULTIPLY', magnitude, 2, clamp=True))
    small = g.math('MINIMUM', inputs['Min Scale'], inputs['Max Scale'])
    large = g.math('MAXIMUM', inputs['Min Scale'], inputs['Max Scale'])
    varying_scale = g.mix(importance, small, large, label='Per-cell glyph size')
    smart_scale = g.math('MINIMUM', g.math('MULTIPLY', inputs['Glyph Scale'],
        g.mix(inputs['Scale Strength'], 1, varying_scale)), 1)
    scale = g.switch(inputs['Match Mode'], inputs['Glyph Scale'], smart_scale, 'Classic or Smart scale')
    local_u = g.math('ADD', g.math('DIVIDE', g.math('SUBTRACT', local_u, 0.5), scale), 0.5)
    local_v = g.math('ADD', g.math('DIVIDE', g.math('SUBTRACT', local_v, 0.5), scale), 0.5)
    bounds = 1.0
    for coordinate in (local_u, local_v):
        bounds = g.math('MULTIPLY', bounds, g.math('GREATER_THAN', coordinate, 0))
        bounds = g.math('MULTIPLY', bounds, g.math('LESS_THAN', coordinate, 1))
    atlas = g.node('CompositorNodeImage', 'Glyph atlas')
    atlas.image = atlas_image
    mask = g.luminance(g.sample(atlas.outputs[0], g.math('DIVIDE', g.math('ADD', index, local_u), len(ramp) + 4, label='Atlas U'), local_v, 'Glyph lookup', nearest=True), 'Glyph mask')
    mask = g.math('MULTIPLY', mask, bounds)
    separate = g.node('CompositorNodeSeparateColor', 'Source alpha')
    g.put(separate.inputs[0], sampled)
    mask = g.math('MULTIPLY', mask, separate.outputs['Alpha'])
    color = g.node('ShaderNodeVectorMath', 'Color brightness')
    color.operation = 'SCALE'
    g.put(color.inputs[0], sampled)
    g.put(color.inputs['Scale'], inputs['Color Gain'])
    ink = g.mix(inputs['Color Mode'], inputs['Foreground'], color.outputs['Vector'], color=True, label='Monochrome or color')
    albedo_info = g.node('CompositorNodeImageInfo', 'Albedo availability')
    g.put(albedo_info.inputs[0], inputs['Albedo'])
    albedo_available = g.math('GREATER_THAN', g.separate(albedo_info.outputs['Dimensions'], 'Albedo dimensions')[0], 1)
    color_source = g.mix(albedo_available, original, inputs['Albedo'], color=True, label='Albedo or Combined fallback')
    averaged_color = smart.blur(g, color_source, dimensions, columns, rows, 0.35, 'Smart color averaging')
    smart_color = g.sample(averaged_color, center_u, center_v, 'Smart cell color')
    smart_ink = g.mix(inputs['Color Mode'], inputs['Foreground'], smart_color, color=True)
    smart_ink = smart.readable_color(g, smart_ink, inputs['Background'],
        g.mix(inputs['Color Mode'], 1, inputs['Saturation']),
        g.mix(inputs['Color Mode'], 1, inputs['Color Gain']), inputs['Minimum Contrast'])
    ink = g.switch(inputs['Match Mode'], ink, smart_ink, 'Classic or Smart ink', color=True)
    background = g.mix(inputs['Transparent'], inputs['Background'], (0, 0, 0, 1), color=True, label='Background color')
    art = g.mix(mask, background, ink, color=True, label='Draw glyphs')
    alpha = g.node('CompositorNodeSetAlpha', 'Output transparency')
    alpha.inputs['Type'].default_value = 'Replace Alpha'
    g.put(alpha.inputs['Image'], art)
    g.put(alpha.inputs['Alpha'], g.mix(inputs['Transparent'], 1, mask))
    art = alpha.outputs[0]
    channels = g.node('CompositorNodeSeparateColor', 'Object and world coverage')
    g.put(channels.inputs[0], inputs['Object Mask'])
    excluded = g.math('MULTIPLY', channels.outputs['Red'], 1, clamp=True)
    surface = g.math('MULTIPLY', channels.outputs['Green'], 1, clamp=True)
    world_ascii = g.math('COMPARE', inputs['World Mode'], 0)
    world_solid = g.math('COMPARE', inputs['World Mode'], 2)
    world_transparent = g.math('COMPARE', inputs['World Mode'], 3)
    world_replaced = g.math('ADD', world_solid, world_transparent)
    world_color = g.mix(world_transparent, inputs['Background'], (0, 0, 0, 0),
                       color=True, label='World replacement')
    world_base = g.mix(surface, world_color, original, color=True, label='Preserve native surfaces')
    base = g.mix(world_replaced, original, world_base, color=True, label='Original or replaced world')
    coverage = g.mix(world_ascii, surface, 1, label='Include world in ASCII')
    coverage = g.math('SUBTRACT', coverage, excluded, clamp=True)
    # Only pixels with an actual included-surface contribution are hardened.
    # Thresholding 1-excluded would also eat native objects' antialiased edges.
    included = g.math('SUBTRACT', surface, excluded, clamp=True)
    edge_coverage = g.math('GREATER_THAN', included, inputs['Edge Coverage Threshold'])
    coverage = g.mix(g.math('MULTIPLY', inputs['Remove Original Edge'], edge_coverage),
                     coverage, 1, label='Remove native surface fringe')
    selective = g.mix(coverage, base, art, color=True, label='Object and world selection')
    # An unavailable Cycles viewport pass is a constant, not an image. Keep the
    # full-image ASCII preview in that case; EEVEE supplies the actual AOV.
    mask_info = g.node('CompositorNodeImageInfo', 'Mask image availability')
    g.put(mask_info.inputs[0], inputs['Object Mask'])
    mask_dimensions = g.separate(mask_info.outputs['Dimensions'], 'Mask dimensions')
    available = g.math('GREATER_THAN', mask_dimensions[0], 1)
    selected_art = g.mix(g.math('MULTIPLY', inputs['Use Object Mask'], available),
                         art, selective, color=True, label='Selective or full-frame ASCII')
    result = g.mix(g.math('MULTIPLY', inputs['Strength'], inputs['Enabled']), original, selected_art, color=True, label='Effect strength')
    output = g.node('NodeGroupOutput', 'ASCII output')
    g.put(output.inputs['Image'], result)
    return tree


def effect_node(scene):
    tree = scene.compositing_node_group
    if tree:
        return next((node for node in tree.nodes if node.get(OWNER) and node.type == 'GROUP'), None)
    return None


def bind_controls(node, scene):
    for name, socket_type, prop, expression in CONTROLS:
        socket = node.inputs[name]
        value = getattr(scene.ascii_render, prop)
        if scene.ascii_render.bl_rna.properties[prop].type == 'ENUM':
            value = next(item.value for item in scene.ascii_render.bl_rna.properties[prop].enum_items
                         if item.identifier == value)
        socket.default_value = value
        components = range(4) if socket_type == 'NodeSocketColor' else (None,)
        for component in components:
            fcurve = socket.driver_add('default_value') if component is None else socket.driver_add('default_value', component)
            driver = fcurve.driver
            driver.type = 'SCRIPTED'
            for old_variable in list(driver.variables):
                driver.variables.remove(old_variable)
            variable = driver.variables.new()
            variable.name = 'value'
            variable.type = 'SINGLE_PROP'
            target = variable.targets[0]
            target.id_type = 'SCENE'
            target.id = scene
            target.data_path = f'ascii_render.{prop}' + ('' if component is None else f'[{component}]')
            driver.expression = expression


def freeze_controls(node):
    """Keep the native effect usable when this extension is disabled."""
    for name, socket_type, _, _ in CONTROLS:
        socket = node.inputs.get(name)
        if socket is None:
            continue  # Older saved node groups may not have the newer controls.
        value = tuple(socket.default_value) if socket_type == 'NodeSocketColor' else socket.default_value
        socket.driver_remove('default_value')
        socket.default_value = value


def upgrade(scene):
    node = effect_node(scene)
    if node is None or node.node_tree.get('ascii_schema', 0) >= SCHEMA:
        return
    old = node.node_tree
    links = [(socket.name, socket.links[0].from_socket) for socket in node.inputs if socket.is_linked]
    values = {socket.name: socket.default_value[:] if socket.type in {'RGBA', 'VECTOR'} else socket.default_value
              for socket in node.inputs if hasattr(socket, 'default_value')}
    freeze_controls(node)
    node.node_tree = build_effect(scene.ascii_render)
    for name, value in values.items():
        if name in node.inputs:
            if isinstance(node.inputs[name], bpy.types.NodeSocketBool):
                value = bool(value)
            node.inputs[name].default_value = value
    for name, source in links:
        if name in node.inputs:
            scene.compositing_node_group.links.new(source, node.inputs[name])
    bind_controls(node, scene)
    if old.users == 0:
        bpy.data.node_groups.remove(old)


def install(scene):
    existing = effect_node(scene)
    if existing:
        upgrade(scene)
        from .coverage import sync_scene
        sync_scene(scene)
        return existing
    tree = scene.compositing_node_group
    if tree is None:
        tree = bpy.data.node_groups.new(f'{scene.name} • Compositor', 'CompositorNodeTree')
        tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        scene.compositing_node_group = tree
        source = tree.nodes.new('CompositorNodeRLayers')
        source.location = (0, 0)
        output = tree.nodes.new('NodeGroupOutput')
        output.location = (600, 0)
        tree.links.new(source.outputs['Image'], output.inputs['Image'])
    elif tree.library:
        raise RuntimeError('Make the scene compositor local before adding ASCII Render')
    elif tree.users > 1:
        # Scene-specific drivers must never affect another scene sharing a tree.
        tree = tree.copy()
        scene.compositing_node_group = tree
    output = next((n for n in tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output), None)
    if output is None:
        raise RuntimeError('The scene compositor needs an active Group Output node')
    image_input = next((s for s in output.inputs if s.type == 'RGBA'), None)
    if image_input is None:
        raise RuntimeError('The compositor Group Output needs a Color image socket')
    original_source = image_input.links[0].from_socket if image_input.is_linked else None
    effect = build_effect(scene.ascii_render)
    node = tree.nodes.new('CompositorNodeGroup')
    node.node_tree = effect
    node.name = 'ASCII Render'
    node.label = 'ASCII Render'
    node[OWNER] = True
    node.use_custom_color = True
    node.color = (0.10, 0.28, 0.22)
    node.location = (output.location.x - 240, output.location.y)
    node.width = 220
    try:
        bind_controls(node, scene)
        if original_source:
            tree.links.new(original_source, node.inputs['Image'])
            # Keep a Viewer that was showing this same final image in sync.
            for viewer in tree.nodes:
                if viewer.type == 'VIEWER' and viewer.inputs[0].is_linked and viewer.inputs[0].links[0].from_socket == original_source:
                    tree.links.new(node.outputs['Image'], viewer.inputs[0])
        else:
            node.inputs['Image'].default_value = tuple(image_input.default_value)
        tree.links.new(node.outputs['Image'], image_input)
    except Exception:
        tree.nodes.remove(node)
        bpy.data.node_groups.remove(effect)
        raise
    scene.render.use_compositing = True
    from .coverage import sync_scene
    sync_scene(scene)
    return node


def refresh_atlas(scene):
    node = effect_node(scene)
    if node is None:
        return
    ramp = character_ramp(scene.ascii_render)
    tree = node.node_tree
    old_images = [n.image for n in tree.nodes if n.type == 'IMAGE' and n.image]
    atlas = atlas_for(ramp)
    tree.nodes['Glyph atlas'].image = atlas
    for name, image in zip(('Glyph descriptors', 'Glyph features', 'Glyph density order'), smart.descriptors_for(atlas)):
        tree.nodes[name].image = image
    tree.nodes['Fill glyph index'].inputs[1].default_value = len(ramp)
    tree.nodes['Last fill index'].inputs[1].default_value = len(ramp) - 1
    tree.nodes['Contour atlas offset'].inputs[1].default_value = len(ramp)
    tree.nodes['Atlas U'].inputs[1].default_value = len(ramp) + 4
    count = len(ramp) + 4
    candidates = len(set(ramp + '-|/\\'))
    tree.nodes['Smart rank count'].inputs[1].default_value = candidates - 1
    for offset in (0, -1, 1, -2, 2):
        tree.nodes[f'Smart candidate {offset}'].inputs[1].default_value = candidates - 1
        tree.nodes[f'Descriptor U {offset}'].inputs[1].default_value = candidates
        tree.nodes[f'Smart atlas count {offset}'].inputs[1].default_value = count - 1
    for old in old_images:
        if old.users == 0 and old.get(OWNER):
            bpy.data.images.remove(old)


def remove(scene):
    from .viewport import restore
    restore(scene)
    node = effect_node(scene)
    if node is None:
        return
    tree = scene.compositing_node_group
    source = node.inputs['Image'].links[0].from_socket if node.inputs['Image'].is_linked else None
    value = tuple(node.inputs['Image'].default_value)
    destinations = [link.to_socket for link in node.outputs['Image'].links]
    effect = node.node_tree
    # Drivers belong to the containing tree, not to the group being removed.
    for name, socket_type, _, _ in CONTROLS:
        node.inputs[name].driver_remove('default_value')
    tree.nodes.remove(node)
    from .coverage import OWNED, cleanup_unused
    for helper in list(tree.nodes):
        if helper.get(OWNED) == 'source':
            tree.nodes.remove(helper)
    for socket in destinations:
        if source:
            tree.links.new(source, socket)
        else:
            socket.default_value = value
    if effect.users == 0:
        images = [n.image for n in effect.nodes if n.type == 'IMAGE' and n.image]
        bpy.data.node_groups.remove(effect)
        for image in images:
            if image.users == 0 and image.get(OWNER):
                bpy.data.images.remove(image)
    cleanup_unused()
