// /whg/webpack/js/mapAndTable.js

import '../css/mapAndTable.css';
import '../css/mapAndTableAdditional.css';

import { init_mapControls } from './mapControls';
import { recenterMap, initObservers, initOverlays, initPopups } from './mapFunctions';
import { toggleFilters } from './mapFilters';
import { initUtils, initInfoOverlay, startSpinner, minmaxer, get_ds_list_stats, deepCopy } from './utilities';
import { initialiseTable } from './tableFunctions';
import { init_collection_listeners } from './collections';
import SequenceArcs from './mapSequenceArcs';
import { add_to_collection } from './collections.js';

let ds_listJSON = document.getElementById('ds_list_data') || false;
if (ds_listJSON) {
	window.ds_list = JSON.parse(ds_listJSON.textContent);
}
console.log('Dataset list:',window.ds_list);

window.mapBounds;
window.highlightedFeatureIndex;
window.additionalLayers = []; // Keep track of added map sources and layers - required for baselayer switching

window.dateline = null;
let datelineContainer = null;
let mapSequencer = null;
let sequenceArcs;

let table;
let checked_rows;

let spinner_table;
let spinner_detail;
let spinner_map = startSpinner("dataset_content", 3);

let mapParameters = { 
	maxZoom: 10,
	downloadMapControl: true,
    fullscreenControl: true,
	temporalControl: {
        fromValue: 1550,
        toValue: 1720,
        minValue: -2000,
        maxValue: 2100,
        open: false,
        includeUndated: true, // null | false | true - 'false/true' determine state of select box input; 'null' excludes the button altogether
        epochs: null,
        automate: null,
    },
    sequencerControl: true,
    controls: {
	    sequencer: true,
	},
}
let mappy = new whg_maplibre.Map(mapParameters);

const mapLoadPromise = new Promise(function (resolve, reject) {
    mappy.on('load', function () {
        console.log('Map loaded.');
        resolve();
    });
});

let dataLoadPromises = [];
window.ds_list.forEach(function (ds) { // fetch data
    const promise = new Promise(function (resolve, reject) {
		
		ds.ds_id = `${ds.ds_type || 'datasets'}_${ds.id}`;
		$.get(`/${ ds.ds_id.replace('_','/') }/mapdata`, function (data) { // ds_type may alternatively be 'collections'			
		
		    // Merge additional properties from data to ds
		    for (const prop in data) {
		        if (!ds.hasOwnProperty(prop)) {
		            ds[prop] = data[prop];
		        }
		    }        
        
			console.log('data', data);
            for (const prop in data) {
                if (!ds.hasOwnProperty(prop)) {
                    ds[prop] = data[prop];
                }
            }
            console.log(`Dataset "${ds.title}" loaded.`);
            resolve();
        });
    });
    dataLoadPromises.push(promise);
});

Promise.all([mapLoadPromise, ...dataLoadPromises, Promise.all(datatables_CDN_fallbacks.map(loadResource))])
.then(function () {
	
	initOverlays(mappy.getContainer());
	
	let allFeatures = [];
	let allExtents = [];
	
	window.ds_list.forEach(function(ds) {
		ds.features.forEach(feature => {
		    feature.properties = feature.properties || {};
		    feature.properties.dsid = ds.id;
		    feature.properties.dslabel = ds.label;
		    feature.properties.ds_id = ds.ds_id; // Required for table->map linkage
		});
		allFeatures.push(...ds.features);
		if (!!ds.tilesets && ds.tilesets.length > 0) {
			allExtents.push(ds.extent);
		}
		mappy
		.newSource(ds) // Add source - includes detection of tileset availability
		.newLayerset(ds.ds_id); // Add standard layerset (defined in `layerset.js` and prototyped in `whg_maplibre.js`)
	});
	console.log('Added layerset(s).', mappy.getStyle().layers);
	
	window.ds_list_stats = get_ds_list_stats(allFeatures, allExtents);
	console.log('window.ds_list_stats', window.ds_list_stats);
		
	// Initialise Data Table
	const tableInit = initialiseTable(allFeatures, checked_rows, spinner_table, spinner_detail, mappy);
	table = tableInit.table;
	checked_rows = tableInit.checked_rows;

	window.mapBounds = window.ds_list_stats.extent;
	
	// Initialise Map Popups
	initPopups(table);
	
	// Initialise Map Controls
	const mapControlsInit = init_mapControls(mappy, datelineContainer, toggleFilters, mapParameters, table);
	datelineContainer = mapControlsInit.datelineContainer;
	mapSequencer = mapControlsInit.mapSequencer;
	mapParameters = mapControlsInit.mapParameters;
	
	// Initialise Info Box state
	initInfoOverlay();
	
	if (window.ds_list[0].ds_type == 'collections') {
		let tableOrder = null;
		function updateVisualisation(newTableOrder) {
			tableOrder = deepCopy(newTableOrder);
						
			if (sequenceArcs) sequenceArcs = sequenceArcs.destroy();
		    const facet = table.settings()[0].aoColumns[tableOrder[0]].mData.split('.')[1];
		    const order = tableOrder[1];
		    console.log(`Re-sorted by facet: ${facet} ${order}`);
		    
		    if (!!visParameters[facet]) {
				toggleFilters(visParameters[facet]['temporal_control'] == 'filter', mappy, table);			
			    dateline.toggle(visParameters[facet]['temporal_control'] == 'filter');
			    mapSequencer.toggle(visParameters[facet]['temporal_control'] == 'player');
			    const featureCollection = {type:'FeatureCollection',features:allFeatures}
			    if(visParameters[facet]['trail']) {
			    	sequenceArcs = new SequenceArcs(mappy, featureCollection, { facet: facet, order: order });
				}
			}
			else {
				toggleFilters(false, mappy, table);
				dateline.toggle(false);
				mapSequencer.toggle(false);
			}		    
		}
		updateVisualisation(table.order()[0]); // Initialise
		$('#placetable').on('order.dt', function () { // Also fired by table.draw(), so need to track the order
			const newTableOrder = deepCopy(table.order()[0]);
			if (newTableOrder[0] !== tableOrder[0] || newTableOrder[1] !== tableOrder[1]) {
		    	updateVisualisation(newTableOrder);
			}
		});		
	}
	else {
		allFeatures = null; // release memory
	}
	
	// Initialise resize observers
	initObservers();
	
	recenterMap();
	mappy.getContainer().style.opacity = 1;
	
	initUtils(mappy); // Tooltips, ClipboardJS, clearlines, help-matches
	
	init_collection_listeners(checked_rows);
	
	spinner_map.stop();
});

export { mappy };

// TODO: Seemingly-redundant JavaScript not implemented in modularisation
/*
// TODO: add a 'big?' boolean to ds_list based on count of polygons
mappy.on('sourcedata', function (e) {
    // console.log('source_list', source_list)
    if (source_list.includes('territorios892')) {
        // big polygons
        if (e.sourceId == 'territorios892' && e.isSourceLoaded) {
            spinner_map.stop()
            $(".toomany").html('').hide()
        }
    } else {
        spinner_map.stop()
        $(".toomany").html('').hide()
    }
});

    var hideAllPopovers = function () {
        $('.pop-dataset').each(function () {
            $(this).popover('hide');
        });
    };

    var dspop = $(".pop-dataset").popover({
        trigger: 'focus',
        placement: 'right',
        html: true
    }).on('show.bs.popover', function () {
        $.ajax({
            url: '/api/datasets/',
            data: {
                id: $(this).data('id')
            },
            dataType: "JSON",
            async: false,
            success: function (data) {
                ds = data.results[0]{
                     # console.log('ds', ds) #
                }
                html = '<p class="thin"><b>Title</b>: ' + ds.title + '</p>'
                    html += '<p class="thin"><b>Description</b>: ' + ds.description + '</p>'
                    html += '<p class="thin"><b>WHG Owner</b>: ' + ds.owner + '</p>'
                    html += '<p class="thin"><b>Creator</b>: ' + ds.creator + '</p>'
                    dspop.attr('data-content', html);
            }
        });
    })
*/

