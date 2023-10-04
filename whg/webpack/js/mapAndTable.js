// /whg/webpack/js/mapAndTable.js

import { init_mapControls } from './mapControls';
import { addMapSource, addMapLayer, recenterMap, initObservers, initOverlays, initPopups, logSourcesAndLayers } from './mapFunctions';
import { initUtils, initInfoOverlay, startSpinner, get_ds_list_stats } from './utilities';
import { initialiseTable } from './tableFunctions';
import { init_collection_listeners } from './collections';
import datasetLayers from './mapLayerStyles';

console.log('Dataset list:', ds_list); // Embedded in page by Django template
let ds_list_stats;
let allFeatures = [];

let mapStoredBounds;

let spinner_map = startSpinner("dataset_content", 3);

let style_code;
if (mapParameters.styleFilter.length == 0) {
	style_code = ['DATAVIZ', 'DEFAULT']
} else {
	style_code = mapParameters.styleFilter[0].split(".");
}
		
maptilersdk.config.apiKey = mapParameters.mapTilerKey;
let mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	style: maptilersdk.MapStyle[style_code[0]][style_code[1]],
	attributionControl: false,
	geolocateControl: false,
	navigationControl: false,
    userProperties: true
});

const mapLoadPromise = new Promise(function (resolve, reject) {
    mappy.on('load', function () {
        console.log('Map loaded.');
        resolve();
    });
});

let dataLoadPromises = [];
ds_list.forEach(function (ds) { // fetch data
    const promise = new Promise(function (resolve, reject) {
        $.get(`/${ ds.ds_type || 'datasets' }/${ ds.id }/mapdata`, function (data) { // ds_type may alternatively be 'collections'
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

Promise.all([mapLoadPromise, ...dataLoadPromises])
.then(function () {
	
	initOverlays();
	
	ds_list.forEach(function(ds) {
		addMapSource(ds);
		ds.features.forEach(feature => {
		    feature.properties = feature.properties || {};
		    feature.properties.dsid = ds.id;
		    feature.properties.dslabel = ds.label;
		});
		allFeatures.push(...ds.features);
	});
	
	ds_list_stats = get_ds_list_stats(allFeatures);
	console.log('ds_list_stats', ds_list_stats);
	
	datasetLayers.forEach(function(layer) { // Ensure proper layer order for multiple datasets
		ds_list.forEach(function(ds) {
			addMapLayer(layer, ds);
		});
	});
	
	mappy.removeSource('maptiler_attribution');
	// logSourcesAndLayers();
	// TODO: Adjust attribution elsewhere: © MapTiler © OpenStreetMap contributors
		
	// Initialise Data Table
	initialiseTable();

	mapStoredBounds = ds_list_stats.extent;

	// Initialise Map Popups
	initPopups();
	
	// Initialise Map Controls
	init_mapControls();
	
	// Initialise Info Box state
	initInfoOverlay();
	
	// Initialise resize observers
	initObservers();
	
	recenterMap();
	mappy.getContainer().style.opacity = 1;
	
	initUtils(); // Tooltips, ClipboardJS, clearlines, help-matches
	
	init_collection_listeners();
	
	spinner_map.stop();
});

export { mappy, mapStoredBounds, ds_list_stats, allFeatures, spinner_map };

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

