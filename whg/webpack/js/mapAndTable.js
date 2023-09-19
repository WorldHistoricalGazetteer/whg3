// /whg/webpack/js/mapAndTable.js

import datasetLayers from './mapLayerStyles';
import { initMapStyleControl, init_mapControls } from './mapControls';
import { recenterMap, filteredLayer, initObservers, initOverlays, initPopups } from './mapFunctions';
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
let features;
let highlightedFeatureIndex;

let activePopup;

let dateline = null;
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
			const tableInit = initialiseTable(features, checked_rows, spinner_table, spinner_detail);
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
			mappy.addLayer(filteredLayer(layer, dateline));
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
			
			whgMap.style.opacity = 1;
		
			// Initialise Map Popups
			initPopups(mappy, datasetLayers, activePopup, table);
			
			// Initialise Map Controls
			const mapControlsInit = init_mapControls(mappy, dateline, datelineContainer, toggleFilters, mapParameters, data);
			dateline = mapControlsInit.dateline;
			datelineContainer = mapControlsInit.datelineContainer;
			mapParameters = mapControlsInit.mapParameters;
			
		}
		
		console.log('Data layers added, map fitted.');
		console.log('Bounds:', window.mapBounds);
		console.log('Padding:', window.mapPadding);
		/*spinner_map.stop()*/

	}) // get
}

initUtils(mappy); // Tooltips, ClipboardJS, clearlines

init_collection_listeners(checked_rows);

// Apply/Remove filters when dateline control is toggled
$("body").on("click", ".dateline-button", function() {
	toggleFilters( $('.range_container.expanded').length > 0 );
});

// Custom search function to filter table based on dateline.fromValue and dateline.toValue
$.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
	if ( $('.range_container.expanded').length == 0) { // Is dateline inactive?
		return true;
	}
	
    const fromValue = dateline.fromValue;
    const toValue = dateline.toValue;
    const includeUndated = dateline.includeUndated
    
    // Get the min and max values from the data attributes of the row
    const row = $(settings.aoData[dataIndex].nTr);
    const minData = row.attr('data-min');
    const maxData = row.attr('data-max');

    // Convert minData and maxData to numbers for comparison
    const min = minData === 'null' ? 'null' : parseFloat(minData);
	const max = maxData === 'null' ? 'null' : parseFloat(maxData);

    // Filter logic
	if (((!isNaN(fromValue) && !isNaN(toValue)) && (min !== 'null' && max !== 'null' && min <= toValue && max >= fromValue)) || (includeUndated && (min === 'null' || max === 'null'))) {
        return true; // Include row in the result
    }
    return false; // Exclude row from the result
});

function toggleFilters(on){
    datasetLayers.forEach(function(layer){
		mappy.setFilter(layer.id, on ? filteredLayer(layer, dateline).filter : layer.filter);
	});
	table.draw();
}

// TODO: use datatables methods?
// Listen for table row click (assigned using event delegation to allow for redrawing)
$("body").on("click", "#placetable tbody tr", function() {
	const pid = $(this)[0].cells[0].textContent
	
	// highlight this row, clear others
	var selected = $(this).hasClass("highlight-row");
	$("#placetable tr").removeClass("highlight-row");

	if (!selected)
		$(this).removeClass("rowhover");
	$(this).addClass("highlight-row");
	
	// fetch its detail
	getPlace(pid, spinner_detail);
	
	highlightedFeatureIndex = highlightFeature(pid, highlightedFeatureIndex, features, mappy);

});
