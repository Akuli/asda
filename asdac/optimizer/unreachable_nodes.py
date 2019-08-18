# unreachable nodes never end up in the resulting opcode
# this is needed because:
#   - unreachable nodes makes the optimized graphs look ugly (bad for debuging)
#   - some optimizations check how many items there are in a jumped_from list,
#     and if there are too many (because unreachable nodes), they do nothing
#   - could make the compiler use less memory when compiling large files

from asdac import decision_tree


def optimize_unreachable_nodes(root_node, all_nodes):
    # all_nodes are actually all the reachable nodes
    #
    # variables are named like in this pic:
    #
    # Start
    #   \
    #    ...    unreachable
    #       \    /
    #     reachable
    #         |
    #        ...
    unreachable_nodes = decision_tree.get_unreachable_nodes(all_nodes)
    if not unreachable_nodes:
        return False

    for unreachable in unreachable_nodes:
        for reachable in unreachable.get_jumps_to():
            if reachable in unreachable_nodes:
                # will be handled when other nodes get removed
                continue

            for ref in reachable.jumped_from.copy():
                if ref.objekt is unreachable:
                    reachable.jumped_from.remove(ref)

    assert not decision_tree.get_unreachable_nodes(all_nodes)
    return True
