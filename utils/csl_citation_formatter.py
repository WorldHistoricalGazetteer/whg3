# utils/csl_citation_formatter

import json
import re

from django.conf import settings
from nameparser import HumanName


def csl_citation(self):
    try:
        def create_author_dict(person, orcid=None):
            given = f"{person.first} {person.middle}".strip() if person.middle else person.first
            author_dict = {
                "family": person.last or "Unknown",
                "given": given or "",
            }
            if orcid:
                author_dict["ORCID"] = f"https://orcid.org/{orcid}"
            return author_dict

        def parse_names(names):
            authors = []
            name_parts = [name.strip() for name in names.split(';') if name.strip()]
            orcid_pattern = re.compile(r'\b\d{4}-\d{4}-\d{4}-\d{4}\b')

            for name in name_parts:
                if name.startswith('[') and name.endswith(']'):
                    # Organisation name (e.g., [Organisation Name])
                    organisation = name[1:-1]  # Remove the brackets
                    authors.append({"literal": organisation})
                else:
                    # Check for ORCID ID
                    orcid_match = orcid_pattern.search(name)
                    orcid = orcid_match.group() if orcid_match else None
                    # Remove ORCID from name for parsing
                    clean_name = orcid_pattern.sub('', name).strip()
                    # Human name
                    person = HumanName(clean_name)
                    authors.append(create_author_dict(person, orcid=orcid))

            return authors

        authors = []

        # If this is a dataset collection, include all related datasets
        if hasattr(self, 'collection_class') and self.collection_class == 'dataset':
            # Access the related datasets for this collection
            objects = self.datasets.all()  # Get all related datasets
            # Push self to front of list to include the collection metadata
            objects = [self] + list(objects)
        else:
            objects = [self]  # Otherwise, just process the current object (self)

        for obj in objects:
            # Parse authors, creators, and contributors from the database fields
            if hasattr(obj, 'authors') and obj.authors:
                authors.extend(parse_names(obj.authors))
            if hasattr(obj, 'creator') and obj.creator:
                authors.extend(parse_names(obj.creator))
            if hasattr(obj, 'contributors') and obj.contributors:
                authors.extend(parse_names(obj.contributors))

        # Deduplicate authors based on the content of the dictionaries
        unique_authors = []
        seen_authors = set()

        for author in authors:
            # Create a frozenset of the author dictionary items for comparison
            author_tuple = frozenset(author.items())
            if author_tuple not in seen_authors:
                seen_authors.add(author_tuple)
                unique_authors.append(author)

        csl_data = {
            "id": self.label if hasattr(self, 'label') else self.id or "Unknown",
            "type": "dataset",
            "title": self.title or "No Title",
            "author": unique_authors,
            "issued": {
                "date-parts": [[self.create_date.year, self.create_date.month,
                                self.create_date.day]] if self.create_date else []
            },
            "URL": self.webpage or "",
            "DOI": f"{settings.DOI_PREFIX}/whg-{self._meta.model_name}-{self.id}" if self.doi else "",
            "publisher": "World Historical Gazetteer",
            "publisher-place": "Pittsburgh, PA, USA",

            # Custom fields (ignored by CSL processors)
            "description": self.description or "",
            "record_count": self.numrows if hasattr(self, 'numrows') else 0,
            **({"source": self.source} if hasattr(self, 'source') else {}),
            **({"source_citation": self.citation} if hasattr(self, 'citation') else {}),
        }
    except Exception as e:
        csl_data = {"error": str(e)}

    return json.dumps(csl_data)
