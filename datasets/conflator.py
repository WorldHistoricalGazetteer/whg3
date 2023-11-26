from places.models import Place  # Import your Django model

# import some_string_similarity_library
# import some_spatial_analysis_library

def calculate_name_similarity(names1, names2):
  print('name1, name2', names1, names2)
  return 0.7

def geometry_overlap(geoms1, geoms2):
  print('geoms1, geoms2', geoms1, geoms2)

def ccode_overlap(ccodes1, ccodes2):
  # ccodes1=['AR','BR']
  # ccodes2=['AR','MX']
  # Convert both country code lists to sets
  set_ccodes1 = set(ccodes1)
  set_ccodes2 = set(ccodes2)

  # Calculate intersection
  intersection = set_ccodes1 & set_ccodes2

  # Scoring logic
  if intersection:
    # Proportional score based on the size of the intersection and the union
    union = set_ccodes1 | set_ccodes2
    score = len(intersection) / len(union)
  elif not set_ccodes1 and not set_ccodes2:
    # Both lists are empty, can be considered as a complete match
    score = 1
  else:
    # No overlap
    score = 0

  return score

def mixed_overlap(obj1, obj2):
  print('obj1, obj2', obj1, obj2)

def calculate_spatial_overlap(geoms1, geoms2, ccodes1, ccodes2):
  # Case 1: Both records have geometries
  if geoms1 and geoms2:
    return geometry_overlap(geoms1, geoms2)

  # Case 2: Both records have country codes
  elif ccodes1 and ccodes2:
    return ccode_overlap(ccodes1, ccodes2)

  # Case 3: Mixed case (one record has geometry, the other has country codes)
  else:
    if geoms1 and ccodes2:
      return mixed_overlap(geoms1, ccodes2)
    elif geoms2 and ccodes1:
      return mixed_overlap(geoms2, ccodes1)
    else:
      return 0  # No spatial data to compare


def is_feature_class_compatible(fc1, fc2):
  print('fc1, fc2', fc1, fc2)

  # Convert both feature class lists to sets
  set_fc1 = set(fc1)
  set_fc2 = set(fc2)

  # Check for at least one match or both are empty
  return bool(set_fc1 & set_fc2) or (not set_fc1 and not set_fc2)


weight_name = 1
weight_spatial = 1
score_threshold = 0.8
def conflate_records(queryset):
    potential_matches = {}

    for p in queryset:
      fclasses1 = p.fclasses if p.fclasses else []
      names1 = [n.toponym for n in p.names.all()]
      ccodes1 = p.ccodes if p.ccodes else []
      geoms1 = [g.geom for g in p.geoms.all()] if p.geoms else []

      # for other_record in queryset.exclude(dataset=record.dataset):
      for p2 in queryset:
        fclasses2 = p2.fclasses if p2.fclasses else []
        names2 = [n.toponym for n in p2.names.all()]
        ccodes2 = p2.ccodes if p2.ccodes else []
        geoms2 = [g.geom for g in p2.geoms.all()] if p2.geoms else []

        if not is_feature_class_compatible(fclasses1, fclasses2):
          continue

        # loc1 and loc2 are either a django geometry or a list of ccodes, e.g. ['BR', 'AR']
        spatial_overlap = calculate_spatial_overlap(geoms1, geoms2, ccodes1, ccodes2)

        name_similarity = calculate_name_similarity(names1, names2)
        combined_score = weight_name * name_similarity + weight_spatial * spatial_overlap

        if combined_score >= score_threshold:
          if p not in potential_matches:
            potential_matches[p] = []
          potential_matches[p].append((p2, combined_score))

    return potential_matches

# Example usage
testid = 29 # historical conflict data
qs = Place.objects.filter(dataset__id=testid)[:20]
matches = conflate_records(qs)

# Further processing of matches
#

