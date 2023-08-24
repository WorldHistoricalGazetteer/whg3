## Contributing to World Historical Gazetteer: software and data development

World Historical Gazetteer (WHG) is an open-source software  project and welcomes collaborators in its ongoing development. Technical Director Karl Grossner (@kgeographer) has been sole developer until now but he and the WHG project team are now actively inviting contributions in both **software development** and **data development**. 

The active version of WHG is 2.1, in [its own repository](https://github.com/WorldHistoricalGazetteer/whgazetteer).

This repository is for Version 3.0, in active development.

If any of the following is of interest, please do not hesitate to get in touch  (karl@kgeographer.org)!

Specifics for individual work items will be appearing soon as GitHub issues, making it easier to find something that fits with developers'  availability and skills. 

### Software development
WHG is a Django application, and its backend makes extensive use of PostgreSQL/PostGIS, Elasticsearch, and Celery+Redis. The front end JavaScript libraries in use include Bootstrap, JQuery, MapLibre/MapBox. There's a bit of D3 and Turf.js. 

Experienced Django developers could help with refining existing features and building new ones, but there are several ways to help that don't involve Django per se, for the front end (mapping, styling, localization), and the backend Elasticsearch indexes.

#### Creating a local instance
This repository is now available as a Docker project. [Details for cloning it are here]() 

#### Front end

_Design and Styling_. We will be refreshing the appearance of the WHG app for v3, and we are open to suggestions.

_Localization and internationalization_. WHG data and user base is global (visitors from 107 countries), but the site is entirely in English. WHG place records include name variants in many languages, but this variety is not explicit in the interface.


#### Place record reconciliation (machine learning)

WHG maintains two Elasticsearch indexes:
- a "union index" where individual records from data contributions are linked by dataset owners in the accessioning step
- an index of ~3.5 million Wikidata place records

Python code is used to perform reconciliation of records from incoming datasets against both, and to search the union index. The algorithms for finding potential matches in both could be improved.

We are keen to develop new approaches to finding matches between place records, and relatively sophisticated machine learning techniques (e.g. custom vector models and embeddings on multiple dimensions) can probably help. If this sounds interesting, please get in touch.

### Data development
Contributors to WHG must upload data in either [Linked Places format](https://github.com/LinkedPasts/linked-places-format) or its simpler "cousin" [LP-TSV](https://github.com/LinkedPasts/linked-places-format/blob/master/tsv_0.4.md). Contributors hold their project data in a variety formats, including  spreadsheets, relational databases, shapefiles, and RDF/XML, and data varies considerably in complexity. In each case, a transformation must be made from the contributor's format and structure to one of the Linked Places formats.

This transformation can be relatively straightforward (copy/pasting columns from a spreadsheet into an LP-TSV template) or quite difficult. It almost always involves some information loss, which is natural and not a prohibitive factor, but decisions are not always simple. 

The WHG team always consults with contributors about this process, and we often perform the transform ourselves - subject to the contributor's approval of course. This **data development** work can involve some combination of spreadsheets, regular expressions, PostgreSQL manipulations, and python scripts. Therefore, anyone with those skills can make a **_huge_** contribution by helping incoming data get into the system, where its creators can manage the reconciliations work that follows.
