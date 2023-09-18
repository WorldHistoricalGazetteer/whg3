// /whg/webpack/js/mapAndTable.js

import Dateline from './dateline';
import datasetLayers from './mapLayerStyles';
import { fullScreenControl, downloadMapControl, StyleControl, init_mapControls } from './mapControls';
import { getMapPadding, filteredLayer, initPopups } from './mapFunctions';
import { attributionString, minmaxer, startSpinner, initUtils } from './utilities';
import { initialiseTable, highlightFeature, resetSearch, filterColumn, clearFilters } from './tableFunctions';
import { init_collection_listeners } from './collections';
import { getPlace } from './getPlace';

let ds_list = document.getElementById('ds_list_data') || false;
if (ds_list) {
	ds_list = JSON.parse(ds_list.textContent);
}
console.log('ds_list',ds_list);

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

let mapPadding;
let mapBounds;
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

if (!!mapParameters.controls.navigation) map.addControl(new maptilersdk.NavigationControl(), 'top-left');

mappy.addControl(new fullScreenControl(), 'top-left');
mappy.addControl(new downloadMapControl(), 'top-left');

let style_code;
if (mapParameters.styleFilter.length !== 1) {
	mappy.addControl(new StyleControl(mappy, renderData), 'top-right');
}
if (mapParameters.styleFilter.length == 0) {
	style_code = ['DATAVIZ', 'DEFAULT']
} else {
	style_code = mapParameters.styleFilter[0].split(".");
}
mappy.setStyle(maptilersdk.MapStyle[style_code[0]][style_code[1]]);

mappy.addControl(new maptilersdk.AttributionControl({
	compact: true
}), 'bottom-right');

mappy.on('load', function() {

	const whgMap = document.getElementById(mapParameters.container);

	const controlContainer = document.querySelector('.maplibregl-control-container');
	controlContainer.setAttribute('id', 'mapControls');
	controlContainer.classList.add('item');

	const mapOverlays = document.createElement('div');
	mapOverlays.id = 'mapOverlays';
	whgMap.appendChild(mapOverlays);

	['left', 'right'].forEach(function(side) {
		const column = document.createElement('div');
		column.classList.add('column', side);
		mapOverlays.appendChild(column);
		const overlays = document.querySelectorAll('.overlay.' + side);
		overlays.forEach(function(overlay) {
			column.appendChild(overlay);
			overlay.classList.add('item');
		})
		if (side == 'left') column.appendChild(controlContainer);
	})
	
	const resizeObserver = new ResizeObserver(entries => {
		mapPadding = getMapPadding(mappy, mapBounds);
	});

	// Recalculate mapPadding whenever its viewport changes size
	resizeObserver.observe(document.getElementById('mapControls'));
	resizeObserver.observe(document.getElementById('mapOverlays'));

	mapBounds = mappy.getBounds();
	mapPadding = getMapPadding(mappy, mapBounds);
	
	whgMap.style.opacity = 1;
	
	/* Close attribution button? */
	if (mapParameters.controls.attribution.open == false) setTimeout(() => {
		var attributionButton = document.querySelector('.maplibregl-ctrl-attrib-button');
		if (attributionButton) {
			attributionButton.dispatchEvent(new MouseEvent('click', {
				bubbles: true,
				cancelable: true,
				view: window
			}));
			document.querySelector('.maplibregl-ctrl-attrib').classList.add('fade-in');
		}
	}, 0);

	//let hilited = null;

	renderData();

});

// fetch and render
function renderData() {
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
		
		const tableInit = initialiseTable(features, checked_rows, spinner_table, spinner_detail);
		table = tableInit.table;
		checked_rows = tableInit.checked_rows;

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

		mapBounds = data.extent; // Used if map is resized
		mappy.fitBounds(mapBounds, {
			padding: mapPadding,
			duration: 0
		});

		if (dateline) {
			dateline.destroy();
			dateline = null;
		}
		if (datelineContainer) {
			datelineContainer.remove();
			datelineContainer = null;
		}

		if (!!mapParameters.controls.temporal) {
			datelineContainer = document.createElement('div');
			datelineContainer.id = 'dateline';
			document.getElementById('mapControls').appendChild(datelineContainer);

			if (data.minmax) {
				const [minValue, maxValue] = data.minmax;
				const range = maxValue - minValue;
				const buffer = range * 0.1; // 10% buffer

				// Update the temporal settings
				mapParameters.controls.temporal.fromValue = minValue;
				mapParameters.controls.temporal.toValue = maxValue;
				mapParameters.controls.temporal.minValue = minValue - buffer;
				mapParameters.controls.temporal.maxValue = maxValue + buffer;
			}

			dateline = new Dateline({
				...mapParameters.controls.temporal,
				onChange: dateRangeChanged
			});
		};
	
		initPopups(mappy, datasetLayers, activePopup, table);
		init_mapControls(mappy);

		console.log('Data layers added, map fitted.');
		console.log('Bounds:', mapBounds);
		console.log('Padding:', mapPadding);
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

function dateRangeChanged(fromValue, toValue){
	// Throttle date slider changes using debouncing
	// Ought to be possible to use promises on the `render` event
	let debounceTimeout;
    function debounceFilterApplication() {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(toggleFilters(true), 300);
    }
    debounceFilterApplication(); 
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
	
	highlightedFeatureIndex = highlightFeature(pid, highlightedFeatureIndex, features, mappy, mapBounds, mapPadding);

});
