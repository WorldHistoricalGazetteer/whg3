from django.apps import apps

model_classes = apps.get_models()
model_full_names = [model._meta.label for model in model_classes]

# Sort in ascending order
model_full_names_sorted_asc = sorted(model_full_names)

print("Ascending order:", model_full_names_sorted_asc)