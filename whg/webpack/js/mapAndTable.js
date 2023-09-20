// /whg/webpack/js/mapAndTable.js

import { initMapStyleControl, init_mapControls } from './mapControls';
import { addMapSources, recenterMap, initObservers, initOverlays, initPopups } from './mapFunctions';
import { toggleFilters } from './mapFilters';
import { initUtils, initInfoOverlay, startSpinner } from './utilities';
import { initialiseTable } from './tableFunctions';
import { init_collection_listeners } from './collections';

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
	initMapStyleControl(mappy, mapParameters);
	initOverlays(whgMap);
	const spinner_map = startSpinner("dataset_content");
	
	const dsid = pageData;

	// fetch data
	$.get('/datasets/' + dsid + '/mapdata', function(data) {
		features = data.features;
		
		// Initialise Info Box state
		initInfoOverlay();
		
		// Initialise Data Table
		const tableInit = initialiseTable(features, checked_rows, spinner_table, spinner_detail, mappy);
		table = tableInit.table;
		checked_rows = tableInit.checked_rows;
		
		addMapSources(mappy, data);
	
		window.mapBounds = data.extent;
		recenterMap(mappy);
		
		initObservers(mappy);
	
		// Initialise Map Popups
		initPopups(mappy, activePopup, table);
		
		// Initialise Map Controls
		const mapControlsInit = init_mapControls(mappy, datelineContainer, toggleFilters, mapParameters, data, table);
		datelineContainer = mapControlsInit.datelineContainer;
		mapParameters = mapControlsInit.mapParameters;
		
		whgMap.style.opacity = 1;
		
		initUtils(mappy); // Tooltips, ClipboardJS, clearlines
		
		init_collection_listeners(checked_rows);
		
		spinner_map.stop();

	}) // get
});

