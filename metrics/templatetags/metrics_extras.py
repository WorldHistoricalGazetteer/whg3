from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Returns the value from a dictionary for a given key.
    """
    return dictionary.get(key)