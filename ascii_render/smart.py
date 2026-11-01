"""Bounded, native-node Smart analysis. No image processing in Python at runtime."""

import bpy

from .glyphs import _ROWS, CELL_W, CELL_H


def descriptor(char):
    """2x3 coverage using exactly the packed atlas pixel layout, bottom row first."""
    quadrants = [0.0] * 6
    for row, bits in enumerate(_ROWS[char]):
        for column in range(5):
            if bits & (1 << (4 - column)):
                for dy in range(2):
                    for dx in range(2):
                        x, y = 3 + column * 2 + dx, 5 + (6 - row) * 2 + dy
                        quadrants[(y // 8) * 2 + (x >= CELL_W // 2)] += 1 / 64
    mean = sum(quadrants) / 6
    span = max(max(quadrants) - min(quadrants), 0.08)
    return tuple(0.5 + 0.5 * (value - mean) / span for value in quadrants), mean


def descriptors_for(atlas):
    chars = atlas['ascii_characters']
    entries = sorted(((i, *descriptor(char)) for i, char in enumerate(chars)), key=lambda e: e[2])
    peak = max(e[2] for e in entries) or 1
    count = len(chars)
    first = [v for _, features, _ in entries for v in features[:4]]
    second = [v for i, features, mean in entries for v in (*features[4:], i / (count - 1), mean / peak)]
    # Coverage, rather than ramp position, locates the five-candidate window.
    order = []
    for level in range(256):
        rank = min(range(count), key=lambda j: abs(entries[j][2] / peak - level / 255))
        order.extend((rank / (count - 1), 0, 0, 1))
    images = []
    for suffix, width, pixels in (('Descriptors', count, first),
                                  ('Features', count, second), ('Density Order', 256, order)):
        name = atlas.name.replace('Atlas', suffix)
        image = bpy.data.images.get(name)
        if image is None:
            image = bpy.data.images.new(name, width=width, height=1, alpha=True, float_buffer=True)
            image.colorspace_settings.name = 'Non-Color'
            image.alpha_mode = 'CHANNEL_PACKED'
            image.pixels.foreach_set(pixels)
            image.update()
            image['ascii_render_owned'] = True
            image.pack()
        images.append(image)
    return images


def blur(g, image, dimensions, columns, rows, radius, label):
    node = g.node('CompositorNodeBlur', label)
    node.inputs['Type'].default_value = 'Gaussian'
    g.put(node.inputs['Image'], image)
    g.put(node.inputs['Size'], g.xyz(
        g.math('MULTIPLY', g.math('DIVIDE', dimensions[0], columns), radius),
        g.math('MULTIPLY', g.math('DIVIDE', dimensions[1], rows), radius), 0))
    return node.outputs[0]


def analyze(g, inputs, original, dimensions, columns, rows, u, v):
    channels = g.node('CompositorNodeSeparateColor', 'Smart surface mask')
    g.put(channels.inputs[0], inputs['Object Mask'])
    info = g.node('CompositorNodeImageInfo', 'Smart mask availability')
    g.put(info.inputs[0], inputs['Object Mask'])
    available = g.math('GREATER_THAN', g.separate(info.outputs['Dimensions'], 'Smart mask size')[0], 1)
    surface = g.mix(available, 1, channels.outputs['Green'])
    # Normalize weighted blur by blurred coverage. World samples cannot darken
    # the neighborhood of a surface, even at a partially covered silhouette.
    weighted = g.mix(surface, (0, 0, 0, 1), original, color=True, label='Mask-aware source')
    filtered = blur(g, weighted, dimensions, columns, rows, 0.12, 'Smart subcell filter')
    filtered_weight = blur(g, surface, dimensions, columns, rows, 0.12, 'Subcell coverage filter')
    samples, light = [], []
    for x, y in ((-0.25, -1/3), (0.25, -1/3), (-0.25, 0), (0.25, 0), (-0.25, 1/3), (0.25, 1/3)):
        su = g.math('ADD', u, g.math('DIVIDE', x, columns))
        sv = g.math('ADD', v, g.math('DIVIDE', y, rows))
        sample = g.sample(filtered, su, sv, f'Smart subcell {len(samples)}')
        weight = g.math('MAXIMUM', g.luminance(g.sample(filtered_weight, su, sv,
            'Subcell weight'), 'Subcell coverage'), 1e-4)
        samples.append(sample)
        exposed = g.math('MULTIPLY', g.math('DIVIDE', g.luminance(sample, 'Subcell luminance'), weight),
                         g.math('POWER', 2, inputs['Exposure']))
        light.append(g.math('POWER', g.math('MAXIMUM', exposed, 0), 1 / 2.2))
    total = light[0]
    for value in light[1:]:
        total = g.math('ADD', total, value)
    mean = g.math('MULTIPLY', total, 1/6)
    neighborhood = blur(g, weighted, dimensions, columns, rows, 1.5, 'Local tone neighborhood')
    neighborhood_weight = blur(g, surface, dimensions, columns, rows, 1.5, 'Local coverage neighborhood')
    local = g.luminance(g.sample(neighborhood, u, v, 'Neighborhood mean'), 'Local mean luminance')
    weight = g.math('MAXIMUM', g.luminance(g.sample(neighborhood_weight, u, v,
        'Neighborhood weight'), 'Neighborhood coverage'), 1e-4)
    local = g.math('DIVIDE', local, weight)
    local = g.math('POWER', g.math('MAXIMUM', g.math('MULTIPLY', local,
        g.math('POWER', 2, inputs['Exposure'])), 0), 1 / 2.2)
    low, high = light[0], light[0]
    for value in (*light[1:], local):
        low, high = g.math('MINIMUM', low, value), g.math('MAXIMUM', high, value)
    span = g.math('MAXIMUM', g.math('SUBTRACT', high, low), inputs['Adaptive Floor'])
    adapted = g.math('ADD', 0.5, g.math('MULTIPLY',
        g.math('DIVIDE', g.math('SUBTRACT', mean, local), span), 0.65), clamp=True)
    # Preserve a dark/bright anchor; local normalization alone flattens silhouettes.
    tone = g.mix(g.math('MULTIPLY', inputs['Adaptive Strength'],
        g.math('GREATER_THAN', mean, 0.01)), mean, adapted, label='Local adaptive tone')
    tone = g.math('ADD', g.math('MULTIPLY', g.math('SUBTRACT', tone, 0.5), inputs['Contrast']), 0.5, clamp=True)
    tone = g.math('POWER', tone, g.math('DIVIDE', 1, inputs['Gamma']), clamp=True)
    tone = g.mix(inputs['Invert'], tone, g.math('SUBTRACT', 1, tone))
    pattern = [g.math('DIVIDE', g.math('SUBTRACT', q, mean), span) for q in light]
    pattern = [g.mix(inputs['Invert'], q, g.math('MULTIPLY', q, -1)) for q in pattern]
    dx = g.math('MULTIPLY', g.math('ADD', g.math('ADD', g.math('SUBTRACT', light[1], light[0]),
        g.math('SUBTRACT', light[3], light[2])), g.math('SUBTRACT', light[5], light[4])), 1/3)
    dy = g.math('MULTIPLY', g.math('SUBTRACT', g.math('ADD', light[4], light[5]),
                                g.math('ADD', light[0], light[1])), 0.5)
    return tone, pattern, dx, dy


def match(g, inputs, tone, pattern, ramp, atlas):
    images = []
    for label, atlas_image in zip(('Glyph descriptors', 'Glyph features', 'Glyph density order'), descriptors_for(atlas)):
        image = g.node('CompositorNodeImage', label)
        image.image = atlas_image
        images.append(image.outputs[0])
    count = len(ramp) + 4
    order = g.sample(images[2], tone, 0.5, 'Coverage rank', nearest=True)
    channels = g.node('CompositorNodeSeparateColor', 'Coverage rank value')
    g.put(channels.inputs[0], order)
    seed = g.math('ROUND', g.math('MULTIPLY', channels.outputs[0], count - 1, label='Smart rank count'))
    best_score, best = None, seed
    for offset in (0, -1, 1, -2, 2):
        candidate = g.math('MINIMUM', g.math('MAXIMUM', g.math('ADD', seed, offset), 0),
                           count - 1, label=f'Smart candidate {offset}')
        coord = g.math('DIVIDE', g.math('ADD', candidate, 0.5), count, label=f'Descriptor U {offset}')
        features = g.sample(images[0], coord, 0.5, 'Candidate descriptor', nearest=True)
        separate = g.node('CompositorNodeSeparateColor', 'Descriptor features')
        g.put(separate.inputs[0], features)
        extra = g.node('CompositorNodeSeparateColor', 'Extra descriptor features')
        g.put(extra.inputs[0], g.sample(images[1], coord, 0.5, 'Candidate extra features', nearest=True))
        score = 0
        for a, b in zip(pattern, (*separate.outputs, extra.outputs[0], extra.outputs[1])):
            b = g.math('MULTIPLY', g.math('SUBTRACT', b, 0.5), 2)
            delta = g.math('SUBTRACT', a, b)
            score = g.math('ADD', score, g.math('MULTIPLY', delta, delta))
        distance = g.math('SUBTRACT', extra.outputs[3], tone)
        score = g.math('ADD', g.math('MULTIPLY', g.math('MULTIPLY', score, inputs['Shape Strength']), 1/6),
                       g.math('MULTIPLY', g.math('MULTIPLY', distance, distance), 2))
        atlas_index = g.math('ROUND', g.math('MULTIPLY', extra.outputs[2], count - 1,
            label=f'Smart atlas count {offset}'))
        if best_score is not None:
            wins = g.math('LESS_THAN', score, best_score)
            best = g.mix(wins, best, atlas_index, label='Best shape index')
            best_score = g.math('MINIMUM', score, best_score)
        else:
            best_score = score
            best = atlas_index
    return best


def readable_color(g, color, background, saturation, gain, gap):
    """Keep RGB in gamut and enforce a linear-luminance gap on opaque ink."""
    channels = g.separate(color, 'Smart ink RGB')
    luminance = g.luminance(color, 'Smart color luminance')
    rgb = [g.math('MULTIPLY', g.math('ADD', luminance,
        g.math('MULTIPLY', g.math('SUBTRACT', c, luminance), saturation)), gain, clamp=True)
        for c in channels]
    color = g.xyz(*rgb, label='Saturated cell color')
    luminance = g.luminance(color, 'Ink luminance')
    bg = g.math('MULTIPLY', g.luminance(background, 'Background luminance'), 1, clamp=True)
    need = g.math('LESS_THAN', g.math('ABSOLUTE', g.math('SUBTRACT', luminance, bg)), gap)
    brighter = g.math('LESS_THAN', bg, 0.5)
    target = g.mix(brighter, g.math('SUBTRACT', bg, gap), g.math('ADD', bg, gap))
    factor = g.mix(brighter,
        g.math('DIVIDE', g.math('SUBTRACT', luminance, target), g.math('MAXIMUM', luminance, 1e-6)),
        g.math('DIVIDE', g.math('SUBTRACT', target, luminance), g.math('MAXIMUM',
            g.math('SUBTRACT', 1, luminance), 1e-6)))
    return g.mix(g.math('MULTIPLY', need, factor), color,
                 g.mix(brighter, (0, 0, 0, 1), (1, 1, 1, 1), color=True),
                 color=True, label='Readable Smart ink')
