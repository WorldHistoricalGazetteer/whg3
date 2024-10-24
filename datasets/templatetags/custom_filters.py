from django import template

register = template.Library()


@register.filter
def factored_size(value):
    """
    Converts a file size in bytes into a human-readable format (TB, GB, MB, KB, bytes).
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "Unknown size"

    units = ["bytes", "KB", "MB", "GB", "TB"]
    factor = 1000

    for unit in units:
        if value < factor:
            return f"{value:.1f} {unit}"
        value /= factor

    return f"{value:.1f} TB"  # Fall back to TB if it's larger


@register.filter
def format_label(format_value):
    if format_value == 'json':
        return 'Linked Places format (LPF)'
    elif format_value == 'delimited':
        return 'Delimited (LP-TSV)'
    return f'Delimited ({format_value})'


@register.filter
def strip_media_path(path):
    """Strips any '/app/media/' part from the file path."""
    return path.replace('/media/app/media/', '') if path else path
