import re


def yearspan(timespan):
    def get_year(start_or_end):
        datestring = start_or_end.get('earliest', start_or_end.get('in', start_or_end.get('latest', None)))
        if not isinstance(datestring, str):
            return None
        if datestring:
            match = re.match(r'(-?\d{1,5})(-(0[1-9]|1[0-2]))?(-([0-2][0-9]|3[01]))?', datestring)
            if match:
                return int(match.group(1))
        return None

    start = get_year(timespan.get('start', {}))
    end = get_year(timespan.get('end', {}))
    if not start and not end:
        return None
    return [start if start is not None else end, end if end is not None else start]


def merge_yearspans(yearspans):
    # Convert lists to tuples and sort by the start time
    yearspans = [tuple(span) for span in yearspans]
    yearspans.sort()

    merged = []

    for start, end in yearspans:
        if merged and start <= merged[-1][1]:  # Check overlap
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))  # Merge
        else:
            merged.append((start, end))

    # Remove spanned yearspans and convert back to lists
    return [[s, e] for s, e in merged if not any(ms <= s and me >= e for ms, me in merged if (ms, me) != (s, e))]
