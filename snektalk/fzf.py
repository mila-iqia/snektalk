# Adapted from: https://github.com/amjith/fuzzyfinder
# https://blog.amjith.com/fuzzyfinder-in-10-lines-of-python
# It sorts the results differently from the original, with matches
# ordered by compactness and then index in original list

import re


def fuzzyfinder(input, collection):
    """
    Args:
        input (str): A partial string which is typically entered by a user.
        collection (iterable): A collection of strings which will be filtered
                               based on the `input`.

    Returns:
        suggestions (generator): A generator object that produces a list of
            suggestions narrowed down from `collection` using the `input`.
    """
    suggestions = []
    input = str(input) if not isinstance(input, str) else input
    pat = ".*?".join(map(re.escape, input))
    pat = "(?=({0}))".format(
        pat
    )  # lookahead regex to manage overlapping matches
    regex = re.compile(pat, re.IGNORECASE)
    for idx, item in enumerate(collection):
        r = list(regex.finditer(item))
        if r:
            best = min(r, key=lambda x: len(x.group(1)))  # find shortest match
            suggestions.append((len(best.group(1)), idx, item))

    # print(regex)
    # return (z for z in sorted(suggestions))
    return (z[-1] for z in sorted(suggestions))
