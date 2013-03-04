""""
    Transform XML in usable stuff
"""

__all__ = 'load', 'load_node'

from xml.etree import ElementTree
import itertools
import operator

    
def _sorted_groupby(thing, key=None):
    return itertools.groupby(sorted(thing, key=key), key=key)


def load(file):
    try:
        document = ElementTree.parse(file).getroot()
    except IOError:
        document = ElementTree.fromstring(file)
    return load_node(document, root_tag=True)


def load_node(root, root_tag=False):
    if not isinstance(root, ElementTree.Element):
        return root

    place = {}
    place.update(root.attrib)

    for name, stuff in _sorted_groupby(root, key=operator.attrgetter('tag')):
        objs = [load_node(x) for x in stuff]
        
        if len(objs) == 1:
            objs = objs[0]

        place[name] = objs

    if root_tag:
        place['@tag'] = root.tag

    data = root.text and root.text.strip()
    if data:
        if not place:
            return data
        place['@text'] = data

    if not place:
        return None

    return place

