// /whg/webpack/areas.js

import datasetLayers from './mapLayerStyles';
import { attributionString } from './utilities';
import { bbox } from './6.5.0_turf.min.js';
import { CustomAttributionControl } from './customMapControls';

import '../css/maplibre-common.css';
import '../css/areas.css';

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
	navigationControl: true,
	userProperties: true
});

let nullCollection = {
    type: 'FeatureCollection',
    features: []
}

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
            
            mappy.addSource('places', {
				'type': 'geojson',
			    'data': nullCollection,
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(function(layer) {
				mappy.addLayer(layer);
			});

		    var draw = new MapboxDraw({
		        displayControlsDefault: false,
		        controls: {
		            point: true,
		            line_string: true,
		            polygon: true,
		            trash: true
		        },
		    })
		    mappy.addControl(draw, 'top-left');
		    const drawControls = document.querySelectorAll(".mapboxgl-ctrl-group.mapboxgl-ctrl");
		    drawControls.forEach((elem) => {
		        elem.classList.add('maplibregl-ctrl', 'maplibregl-ctrl-group');
		    });
		    mappy.on('draw.create', updateGeoJSON);
		    mappy.on('draw.delete', updateGeoJSON);
		    mappy.on('draw.update', updateGeoJSON);
		
		    function updateGeoJSON() {
		        var data = draw.getAll();
		        $("textarea#id_geojson").val(data.features.length > 0 ? JSON.stringify(data) : '');
		    }
			
			mappy.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: mapParameters.controls.attribution.open === false,
			}), 'bottom-right');
			
			map_init();
	
			/*
			var attrib_mb = 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, ' +
				'<a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, ' +
				'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
				token_whg = '{{ mbtoken }}',
				mbstyle_url = 'https://api.mapbox.com/styles/v1/{id}/tiles/256/{z}/{x}/{y}?access_token={token}';
		
		
			var satellite = L.tileLayer(mbstyle_url, {
				id: 'mapbox/satellite-streets-v11',
				token: token_whg,
				attribution: attrib_mb
			});
			var osm = L.tileLayer(mbstyle_url, {
				id: 'mapbox/light-v10',
				token: token_whg,
				attribution: attrib_mb
			});
			*/
		
			var watershedStyle = {
				"fillColor": "#993333",
				"color": "#fff",
				"weight": 1,
				"opacity": 0.7,
				"fillOpacity": 0.1
			};
		
			var riverStyle = {
				"color": "#336699",
				"weight": 1
			};
		
			/*
			rivers = new L.GeoJSON.AJAX("/datasets/ne_rivers982/places", {
				style: riverStyle,
				onEachFeature: function(feature, layer) {
					popupOptions = {
						maxWidth: 200
					};
					layer.bindPopup(feature.properties.name + " (" + feature.properties.src_id + ")", popupOptions);
				}
			});
		
			watersheds = new L.GeoJSON.AJAX("/datasets/wri_watersheds/places", {
				style: watershedStyle,
				onEachFeature: function(feature, layer) {
					layer.setStyle({
						"fillColor": random_rgba()
					})
					popupOptions = {
						maxWidth: 200
					};
					layer.bindPopup(feature.properties.name + " (" + feature.properties.src_id + ")", popupOptions);
				}
			})
		
			drawnItems = L.featureGroup().addTo(mappy)
		
			var baseLayers = {
				"OSM": osm,
				"Satellite": satellite
			};
		
			var overlays = {
				"Drawn features": drawnItems,
				"Rivers": rivers,
				"Watersheds": watersheds
			}
		
			layerGroup = L.control.layers(baseLayers, overlays).addTo(mappy);
			baseLayers['OSM'].addTo(mappy)
			//overlays['Rivers'].addTo(mappy)
			*/
            
            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => resolve());
    });
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {

	// area_type = 'ccodes' // default
	$(".textarea").each(function(index) {
		if (["None", "null"].includes($(this).val())) {
			$(this).val('')
		}
	});
	$("#id_geojson").attr("placeholder", "generated from country codes")

 
    })
    .catch(error => console.error("An error occurred:", error));
    
    $('#areas_codes .area-link-clear').click(() => { map_clear(); });
    $('#areas_codes .area-link-render').click(() => { map_render(); });

	$('a[data-toggle="tab"]').on('shown.bs.tab', function(e) {
		const target = $(e.target).attr("href") // activated tab
		const area_type = $(e.target).attr("ref") // activated tab
		map_clear() // switch create modes? clear the deck
		// feed area type to hidden input
		$("input[name='type']").val(area_type)
		console.log('tab id:',target);
		const active = $("ul#area_tabs_ul a.active").attr("href")
		// TODO: better refactor 
		if (target == '#areas_codes') {
			$("#id_geojson").attr("placeholder", "generated from country codes")
			if ($(".leaflet-draw-toolbar").length > 0) {
				// console.log('remove drawControl')
				$(".leaflet-draw").remove()
			}
		} else if (target == '#areas_draw') {
			console.log('line 170', $(".leaflet-draw").length)
			$("#id_geojson").attr("placeholder", "generated from drawn shapes")
			/*
			if ($(".leaflet-draw").length == 0) {
				//drawnItems = L.featureGroup().addTo(mappy)
				drawControls(drawnItems)
				console.log('feature0', drawnItems.toGeoJSON().features[0])
				mappy.on(L.Draw.Event.CREATED, function(event) {
					window.drawnlayer = event.layer;
					console.log('drawnlayer', drawnlayer)
					drawnItems.addLayer(drawnlayer);
					drawnItems.addTo(mappy)
					// $("textarea#id_geojson").val(JSON.stringify(drawnItems.toGeoJSON()))
					$("textarea#id_geojson").val(JSON.stringify(drawnItems.toGeoJSON().features[0].geometry))
				});
				mappy.on(L.Draw.Event.EDITED, function(event) {
					// $("textarea#id_geojson").val(JSON.stringify(drawnItems.toGeoJSON()))
					geom = drawnItems.toGeoJSON().features[0].geometry
					geom_string = JSON.stringify(geom)
					//coords = JSON.stringify(geom.coordinates)
					//console.log('coords', geom)
					//fetchCount(coords)
					$("textarea#id_geojson").val(geom_string)
	
				});
				mappy.on(L.Draw.Event.DELETED, function(event) {
					$("textarea#id_geojson").val(JSON.stringify(drawnItems.toGeoJSON()))
					$("textarea#id_geojson").val(JSON.stringify(drawnItems.toGeoJSON().features[0].geometry))
					//drawnItems.addTo(mappy)
					console.log('you deleted something')
				})
			}
			*/
		}
	});

// ES query to count...retrieve?
function fetchCount(coords) {
	//startMapitSpinner()
	console.log('coords', coords)
	context = {
		"type": "FeatureCollection",
		"features": []
	}
	$.get("/search/context", {
			idx: 'whg',
			extent: coords,
			task: 'count'
		},
		function(data) {
			console.log('this many:', data['count'])
			$("#count_result").html(data['count'])
		});
}
			
function random_rgba() {
	var o = Math.round,
		ra = Math.random,
		s = 255;
	tup = [o(ra() * s), o(ra() * s), o(ra() * s)]

	const rgbToHex = (r, g, b) => '#' + [r, g, b].map(x => {
		const hex = x.toString(16)
		return hex.length === 1 ? '0' + hex : hex
	}).join('')

	return rgbToHex(tup[0], tup[1], tup[2])
}

/*
// add draw controls to map
// on tab switch && on update Area if type == 'drawn'
function drawControls(mode) {
	var drawControl = new L.Control.Draw({
		draw: {
			marker: false,
			polyline: false,
			circle: false,
			circlemarker: false,
		},
		edit: {
			featureGroup: mode
		}
	});
	mappy.addControl(drawControl);
}
*/
function zoomTo(id) {
	mappy.setView(idToFeature[id]._latlng, mappy.getZoom() + 2)
}

function cleanJson(text) {
	z = text.replace(/'/g, '\\"')
	y = z.replace(/point/, 'Point')
	return JSON.parse(JSON.parse(y))
}

function map_init() {
	// whether drawn or ccodes, load existing data
	if (action == 'update') {
		// existing
		areageom = JSON.parse(formGeoJSON)

		// if area was drawn
		if (formType == 'drawn') {
			console.log('was drawn')
			/*
			// load existing for editing
			lgeojson = L.geoJson(areageom, {
				onEachFeature: function(feature, layer) {
					drawnItems.addLayer(layer);
				}
			}).addTo(mappy)
			mappy.fitBounds(lgeojson.getBounds())
			//drawControls(drawnItems)
			*/

			$('a[href="#areas_draw"]').tab('show');
			$('a[href="#areas_codes"]').addClass('disabled').css("cursor", "default")

		} else if (formType == 'ccodes') {
			console.log('was ccodes-generated')
			/*
			window.geom = {
				"type": "FeatureCollection",
				"features": []
			}
			window.buffer = $("input#buffer_km").val()
			cc_layer = L.geoJson(areageom, {
				onEachFeature: function onEachFeature(feature, layer) {
					geom['features'].push(feature)
					//var props = feature.properties;
					//var content = `<p>${props.iso}</p><p>${props.gnlabel}</p>`;
					//layer.bindPopup(content);
				}
			}).addTo(mappy)
			mappy.fitBounds(cc_layer.getBounds())
			*/
			// disable draw tab
			$('a[href="#areas_draw"]').addClass('disabled').css("cursor", "default")
			//map_render()
		}
	}
}

function map_render() {
	console.log('in map_render()')
	let ccodes = $("input#id_ccodes").val()
	window.geoj = $("textarea#id_geojson")
	window.geom = {
		"type": "FeatureCollection",
		"features": []
	}
	window.buffer = $("input#buffer_km").val()
	$("#count_result mark").html('')
	// console.clear()

	var country_url = "/media/data/countries_simplified.json"
	// clear geoJSON
	if (Object.keys(mappy._layers).length > 2) {
		cc_layer.clearLayers()
		hull_layer.clearLayers()
	}
	if (ccodes != '') {
		// TODO: test csv format
		ccode_arr = ccodes.toUpperCase().split(",")
		// console.log(ccode_arr)
		fetch(country_url)
			.then(function(resp) {
				return resp.json();
			})
			.then(function(data) {
				// console.log('fetched data', data)
				/*
				window.cc_layer = L.geoJson(data, {
					filter: function(feature, layer) {
						return ccode_arr.includes(feature.properties.iso);
					},
					onEachFeature: function onEachFeature(feature, layer) {
						// console.log('feature:', JSON.stringify(feature))
						geom['features'].push(feature)
						var props = feature.properties;
						var content = `<p>${props.iso}</p><p>${props.gnlabel}</p>`;
						layer.bindPopup(content);
					}
				}).addTo(mappy);
				*/
			})
			.then(function() {
				hull = turf.buffer(turf.convex(geom), buffer, {
					units: 'kilometers'
				})
				// hull_mp = turf.multiPolygon(hull.geometry.coordinates)
				// geoj.val(JSON.stringify(hull_mp.geometry))
				geoj.val(JSON.stringify(hull.geometry))
				console.log('geoj', geoj.val())
				/*
				hull_layer = L.geoJSON(hull, {
					style: function(feature) {
						return {
							color: '#ff8c00'
						};
					}
				}).addTo(mappy);
				mappy.fitBounds(hull_layer.getBounds())
				*/
			})
	} else {
		alert('Need one or more comma-delimited 2-letter country codes')
	}
}

function map_clear() {
	if (typeof cc_layer != "undefined") {
		cc_layer.remove()
	}
	if (typeof hull_layer != "undefined") {
		hull_layer.remove()
	}
	$("input#id_ccodes").val(null)
	if (action == "create") {
		$("textarea#id_geojson").val(null)
	}
	$("#buffer_km").val(null)
}