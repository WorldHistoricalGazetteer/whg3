### Developer Documentation
The following outlines the software components, architecture, and functionality of the World Historical Gazetteer platform (WHG). The WHG project can still be considered a proof of concept, and might very well warrant structural changes and various enhancements over time, especially as relevant technologies advance. 

#### Software Components
WHG is a Django 4 application, and its backend makes extensive use of PostgreSQL/PostGIS 15-3.4, Elasticsearch 8, and Celery+Redis. The main front end JavaScript libraries in use include Bootstrap, JQuery, and MapLibre/MapBox. There's a bit of D3 and Turf.js. 

#### Webpack
Javascript is managed with webpack. Source files are under `/whg/webpack`. When `npm run build` is run -- automatically on install or manually -- the bundled output is placed in `/whg/static/webpack`. From there Django's collectstatic command copies bundles into the `/static` directory off the root, where they are read by the app. 

A very typical pattern is for a page to have a corresponding `.js` file (and possibly `.css` file), which may themselves reference/import content  from more generic modules used by more than one page.

#### Docker
WHG v3 is a Docker project, configured with Dockerfiles, docker-compose files and several scripts they reference, most held in the `/compose` directory.

The Docker services/containers in use are:

- web
- db (container "postgres")
- webpack
- celery_worker
- celery_beat
- redis
- flower

NOTE: Elasticsearch is not containered. It runs on the WHG production host and includes separate production and development indexes, described below.

#### Elasticsearch
WHG maintains several indexes:

- `wdgn` is a read-only index holding ~13.6 million place records used for reconciliation/geocoding tasks: 3.6m from Wikidata and ~10m from GeoNames.
- `pub` holds records from published datasets that have not yet been fully accessioned (see below), making them discoverable via WHG's search and API functions.
-  `whg` is the project's "union index," where links between individual records across all datasets are recorded. The _accessioning_ workflow step indexes records from published datasets. Records for which we have no prospective matches are added as nominal "parent" or seed records; records that dataset owners approve matches for become nominal "child" records of the matched parents. As published data is indexed to `whg`, its records are removed from `pub`.
-  `whg3dev`is a read/write copy of almost 2 million records taken from `whg` in 2023. It is used in development to test write operations without disturbing the production `whg` index.
-  `pub_dev` is a read/write copy of `pub` used in development.

#### Data stores and pipeline
As outlined above, there are three active data stores in WHG: a PostgrSQL database and the `whg` and `pub` Elasticserch indexes. As such, there is replication. 

The data pipeline is as follows. Status is tracked and the following tags applied as dataset activity proceeds: *uploaded*, *reconciling*, *wd-complete*, *accessioning* and *indexed*. At some stages, Django signals are triggered to perform various functions, e.g. emails to users and admins, and tileset generation.

1. New datasets are created by registered users, by uploading a file in one of two formats: [Linked Places format (LPF)](https://github.com/LinkedPasts/linked-places-format) or [LP-TSV](https://github.com/LinkedPasts/linked-places-format/blob/main/tsv_0.4.md). These were originally created for use in WHG but have since seen uptake by other projects. New datasets are listed in the user's My Data page and managed in a set of private screens. Dataset owners can designate other registered users as collaborators with with either 'member' or 'co-owner' privileges. Now at ***uploaded*** stage.
2. A dataset can be reconciled against the `wdgn` index to augment it with geographic coordinates, additional name variants, and authority identifiers from resources like Wikidata, Getty TGN, VIAF, and several national libraries. Now at ***reconciling*** stage.
3. When all records that had any "hits" in reconciliation have been reviewed, the dataset is now ***wd-complete*** and the owner can request its publication. When metadata is completed, WHG staff can flag the dataset as "public," which indexes its records to the `pub` index and makes them accessible in search and API functions.
4. A further final step is highly encouraged: reconciling the now public dataset to the `whg` union index. This records links between records for the same (actually "closeMatched") place from different datasets. When that task is initiated by WHG staff, the status change to ***accessioning***.
5. When review of potential matches from step 4 is complets, the status becomes ***indexed.***

#### The database
Uploaded data files are validated for adherence to the LPF and/or LP-TSV specifications, then written to a normalized schema in the PostgreSQL database. Tables correspond to the LPF conceptual modelDjango models:

- Dataset
- Place
- PlaceName
- PlaceType
- PlaceGeom
- PlaceLink
- PlaceRelation
- PlaceDescription
- PlaceDepiction

This accomodates the one-to-many attributes involved: a Place can have within its uploaded record any number of names, types, geometries, links, relations, descriptions, and depictions. Furthermore, with the LPF format, names, types, geometries, and relations can be temporally scoped.

Additional models in use:

- Collection (w/`collection_class` of 'place' or 'dataset')
- CollectionGroup (for classroom or workshop scenarios)
- Area (study areas for constraining reconciliation extent)
- TraceAnnotation (annotation of a  Place within a *place collection*)
- Resource (e.g. a contributed lesson plan)

#### Django "apps"
In Django fashion, code related to models is by and large grouped in "app" folders within the project: e.g. places, datasets, collection ('collections' is a reserved word in Python), etc. The `whg` directory holds core config information, and its `urls.py` file directs traffic with numerous `includes`. The `/main` app handles much of the static content, cross-app models and views, etc.

#### Users
WHG uses a custom User model, to allow for extended profile information most readily.

#### Emailing
The system generates various emails: for routine registration and password resets, and to notify users and WHG staff at various stages of activity. The emails are sent using a SendGrid free account. Many are generated by running a `new_emailer()` function that accepts variable insered in the appropriate template.

#### Search
The search function on the Home and Search pages runs against the `whg` and `pub` indexes in tandem. Results from each are differentiated in the results list returned. Those found in `whg` will have an associated *Place Portal* page, where all attestations for the place are aggregated. Those returned from the `pub` index link to a detail page for that single record.

#### Reconciliation
A reconciliation task against the `wdgn` index can be initiated by a dataset owner, and there are several options they can set (e.g. "send all records" or only those missing geometry, and "accept name vaiants" from matched records). It is queued by Celery, and upon completion,

- the user is notified by email
- the resulting hits are queued and presented in the `review.html` page
- users (and any collaborators they designate) review hits per record, one-by-one, deciding whether one or more hits is a **skos:closeMatch** with theirs. In any case (match or no match) they click save and move to the next in the queue.

#### Accessioning
The *accessioning* step is in fact another reconciliation, this time against the `whg` union index. The hits returned in this case will be *sets of index docs* that have been linked by previous accessioning review, using the Elasticsearch parent/child pattern. A parent is simply the first record in for a given place; those that are matched to it in following accessioning tasks for other datasets become children of the parent. There is *nothing special about a parent!* - it is simply the first one in.

#### Place collections
*forthcoming*

#### Collection groups
*forthcoming*

#### Dataset collections
*forthcoming*

#### Maps
*forthcoming*










