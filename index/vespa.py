# index/vespa.py

from django.conf import settings

from vespa.application import Vespa
index = Vespa(url='http://localhost', port=settings.VESPA_ADMIN_PORT)


# def test_vespa_connection():
#     try:
#         # Perform a basic health check or a sample query
#         response = index.query('select * from sources * limit 1')
#         return response
#     except Exception as e:
#         return str(e)


def create_index():
    try:
        schema = '''
        schema my_schema {
            document my_schema {
                field id type int { indexing: attribute | summary }
                field name type string { indexing: index | summary }
                field location type geo { indexing: index | summary }
                field description type string { indexing: index | summary }
            }
        }
        '''
        # Create the schema
        response = index.create_schema(schema)
        return response
    except Exception as e:
        return str(e)
