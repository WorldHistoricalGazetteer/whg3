# validation/views.py
import json
import codecs
import logging
from django.conf import settings
from django.http import HttpResponse
from pyld import jsonld
from .tasks import validate_chunk

logger = logging.getLogger('validation')

def process_lpf(request):
    file_path = '/path/to/large/file.json'
    schema = json.loads(codecs.open(settings.LPF_SCHEMA_PATH, 'r', 'utf8').read())
    context = json.loads(codecs.open(settings.LPF_CONTEXT_PATH, 'r', 'utf8').read())

    def read_json_chunks(file_path, chunk_size=1024*1024):
        with open(file_path, 'r') as file:
            buffer = ""
            for chunk in iter(lambda: file.read(chunk_size), ''):
                buffer += chunk
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        json_ld_doc = json.loads(line)
                        compacted_doc = jsonld.compact(json_ld_doc, context)
                        yield compacted_doc
                    except json.JSONDecodeError:
                        continue

    # Process each chunk with Celery
    for chunk in read_json_chunks(file_path):
        validate_chunk.delay(chunk, schema)

    return HttpResponse("Validation tasks have been triggered.")
