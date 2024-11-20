#
# abbreviated place attribute lists from queryset
# for portal display
# 
def attribListFromSet(attr, qs, exclude_title=None):
  attrib_list=[]
  value='toponym' if attr=='names' else 'sourceLabel'
  for item in qs:
    label = item.jsonb['toponym'] if attr == 'names' \
      else item.jsonb.get('sourceLabel', item.jsonb.get('source_label'))
    # label = item.jsonb['toponym'] if attr == 'names' else item.jsonb['sourceLabel']

    # Exclude the title from the list of variants
    if exclude_title and label == exclude_title:
      continue

    if 'when' in item.jsonb:
      obj = {
        "label": label,
        "timespans": [[int(t['start'][list(t['start'].keys())[0]]),
                       int(t['end'][list(t['end'].keys())[0]])
                       if 'end' in t else
                       int(t['start'][list(t['start'].keys())[0]])]
                      for t in item.jsonb['when']['timespans']]
      }
    else:
      obj={"label": item.jsonb['toponym'] if attr == 'names'
        else item.jsonb.get('sourceLabel', item.jsonb.get('source_label'))}
        # else item.jsonb['sourceLabel']}

    attrib_list.append(obj)
  return attrib_list
