Development priorities, 6 Feb - 5 March
=======================================

Goal is to have all new-in-v3 features functioning **sufficient for team review**

Every click should do what it suggests w/o error, whether it is the ultimate action or not; no long delays - we are demoing

To summarize SG priorities listed below:

- Search debugging; testing w/Selenium? ([issue](../../issues/121))
- wire up vis_parameters w/kg
- set tileset creation signals; expose result in console
- bug: place collection records with no geometry 
- portal page permalink and download link (?prefetch api)
- expose exiting working API endpoints with swagger
	- then, begin Recogito 3 conversation



Base
----
- *one base.html

Home
----
- Announcements (kg)

**Search
--------
- Selenium
- Bloodhound console error: culprit for below?
- clear button in search input works intermittently
- localStorage.clear() required (Chrome)
- odd typeahead results
- Filter Results remain from previous search w/o cache clear
- click of map marker doesn't always scroll list
- select all, clear all doesn't work
- map polygon filter
	- cursor needs to change when active, back when completed
	- completion of a bounds needs to change style


Maps (sg/kg)
------------
- **vis_parameters display options 
	- basemap choice
	- options in ds_summary, place_collection_build, 
			ds_collection_build
	- time slider or player for place collections

- **test tileset creation pipeline
	on public=True if count() > threshold
	confirming geom source (geojson/tileset) in console

- tileset of ecoregions

Portal
------
- *permalink (!)
- *download option(s)
- isolate 'more' link


Publications (ds_gallery)
-------------------------
- confirm all sample datasets, collections are operable (kg)
  - dodgy place collections (13, 19, 4, 6, 8, 1)
  - collection.views.py:355 -> no geometry
  - some load slow: ds.id(local/server) 12(19/4), 13(39/14), 29(29/7) (sim issue to previous (solved) for gallery?)

--- for later ---
- visit a collection, return to collections tab@page?
- indicate place collection div at bottom of card: 'annotated place collection'


Place collections
-----------------
- add places from portal, dataset browse (kg)

API
---
- time permitting, a review of 
	- what works/doesn't
	- what to make public
	- url to a swagger page for devs, then...
	- contact w/Rainer & Jamie

Dashboards
----------
- Admins, staff need 'my data' page too (kg)

