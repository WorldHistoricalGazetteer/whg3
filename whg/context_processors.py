import os

def environment(request):
    return {
        'environment': os.getenv('ENV_CONTEXT', 'default'),
    }
