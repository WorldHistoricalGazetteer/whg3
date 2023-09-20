// /whg/webpack/js/mapAndTable.js

import datasetLayers from './mapLayerStyles';
import { initMapStyleControl, init_mapControls } from './mapControls';
import { recenterMap, initObservers, initOverlays, initPopups } from './mapFunctions';
import { filteredLayer, toggleFilters } from './mapFilters';
import { attributionString, startSpinner, initUtils, initInfoOverlay } from './utilities';
import { initialiseTable, highlightFeature, resetSearch, filterColumn, clearFilters } from './tableFunctions';
import { init_collection_listeners } from './collections';
import { getPlace } from './getPlace';

let ds_list = document.getElementById('ds_list_data') || false;
if (ds_list) {
	ds_list = JSON.parse(ds_list.textContent);
}
console.log('ds_list',ds_list);

const whgMap = document.getElementById(mapParameters.container);

window.mapPadding;
window.mapBounds;
window.highlightedFeatureIndex;
let features;

let activePopup;

window.dateline = null;
let datelineContainer = null;

let table;
let checked_rows;

let spinner_table;
let spinner_detail;
let spinner_map;

maptilersdk.config.apiKey = mapParameters.mapTilerKey;
var mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	attributionControl: false,
	geolocateControl: false,
	navigationControl: false
});

mappy.on('load', function() {
	initMapStyleControl(mappy, renderData, mapParameters);
	initOverlays(whgMap);
	renderData(true);
});

// fetch and render
function renderData(initialise = false) {
	const dsid = pageData;
	// const spinner_map = startSpinner("map_browse");

	// clear any data layers and 'places' source
	datasetLayers.forEach(function(layer, z) {
		if (!!mappy.getLayer(layer.id)) mappy.removeLayer(layer.id);
		if (!!mappy.getLayer('z-index-' + z)) mappy.removeLayer('z-index-' + z);
	});
	if (!!mappy.getSource('places')) mappy.removeSource('places')

	// fetch data
	$.get('/datasets/' + dsid + '/mapdata', function(data) {
		features = data.features;
		
		if (initialise) {
			// Initialise Info Box state
			initInfoOverlay();
			
			// Initialise Data Table
			const tableInit = initialiseTable(features, checked_rows, spinner_table, spinner_detail, mappy);
			table = tableInit.table;
			checked_rows = tableInit.checked_rows;
		}
		
		// add source 'places' w/retrieved data
		mappy.addSource('places', {
			'type': 'geojson',
			'data': data,
			'attribution': attributionString(data),
		})

		// The 'empty' source and layers need to be reset after a change of map style
		if (!mappy.getSource('empty')) mappy.addSource('empty', {
			type: 'geojson',
			data: {
				type: 'FeatureCollection',
				features: []
			}
		});

		datasetLayers.forEach(function(layer, z) {
			mappy.addLayer(filteredLayer(layer));
			mappy.addLayer({
				id: 'z-index-' + (z + 1),
				type: 'symbol',
				source: 'empty'
			});
		});
		
		window.mapBounds = data.extent;
		recenterMap(mappy);
		
		if (initialise) {
		
			initObservers(mappy);
		
			// Initialise Map Popups
			initPopups(mappy, datasetLayers, activePopup, table);
			
			// Initialise Map Controls
			const mapControlsInit = init_mapControls(mappy, datelineContainer, toggleFilters, mapParameters, data, datasetLayers, table);
			datelineContainer = mapControlsInit.datelineContainer;
			mapParameters = mapControlsInit.mapParameters;
			
			whgMap.style.opacity = 1;
			
			initUtils(mappy); // Tooltips, ClipboardJS, clearlines
			
			init_collection_listeners(checked_rows);

		}
		
		/*spinner_map.stop()*/

	}) // get
}
