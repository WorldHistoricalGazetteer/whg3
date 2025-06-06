// /whg/webpack/areas.js
import { CountryCacheFeatureCollection } from './countryCache';
import '../css/areas.css';

let whg_map = new whg_maplibre.Map({
	maxZoom: 10,
    drawingControl: {hide: true}
});

let featureCollection;
let countryCache = new CountryCacheFeatureCollection();

let countryGeoJSON;
var draw;
var $drawControl;

function waitMapLoad() {
	return new Promise((resolve) => {
		whg_map.on('load', () => {
			console.log('Map loaded.');

			addDrawingControl();
			
			// TODO: Removed river and watershed sources and layers, which should be controlled by a style switcher and not added separately
			  
			whg_map
			.newSource('countries') // Add empty source
			.newLayerset('countries', null, 'countries', 'countries');
		
		    whg_map
		    .newSource('hulls')
			.newLayerset('hulls', 'hulls', 'hulls');

			resolve();
		});
	});
}

function waitDocumentReady() {
	return new Promise((resolve) => {
		$(document).ready(() => resolve());
	});
}

Promise.all([
	waitMapLoad(),
	waitDocumentReady(),
	Promise.all(select2_CDN_fallbacks.map(loadResource))
]).then(() => {

    // Populate buffer dropdown options
    const bufferDropdown = $('#buffer_km');
    const bufferOptions = [0, 1, 5, 10, 50, 100, 500, 1000, 5000];
    bufferOptions.forEach(value => {
        bufferDropdown.append(new Option(`${value} km`, value, value === 0 ? true : false));
    });
	bufferDropdown.on('change', updateAreaMap);
		
	if (action == 'update') {
		// existing - assumes that formGeoJSON is a featureCollection
		const areaFeatureCollection = featureGeometryCollection(JSON.parse(formGeoJSON));

		// if area was drawn
		if (formType == 'drawn') {
			console.log('was drawn',areaFeatureCollection)
			draw.set(areaFeatureCollection)
			$('a[href="#areas_draw"]').tab('show');
			// disable ccodes tab
			$('a[href="#areas_codes"]').addClass('disabled').css("cursor", "default");
			$drawControl.show();
		} else if (formType == 'ccodes') {
			console.log('was ccodes-generated')
			whg_map.getSource('hulls').setData(areaFeatureCollection);
			// disable draw tab
			$('a[href="#areas_draw"]').addClass('disabled').css("cursor", "default")
		}
		whg_map.fitBounds(turf.bbox(areaFeatureCollection), {
	        padding: 30,
	        duration: 1000,
	    });
	}
	else {
	  $("textarea#geojson").val('');		
	}
	
    $("#area_form").submit(function(event) {
        if (event.target === $("#area_form")[0]) {
			
			function abort() {
				event.preventDefault();
				alert('Area cannot be saved without any geometries.');				
			}			

		    try {
		        const geojson = JSON.parse($("textarea#geojson").val());
		        // Check for valid GeometryCollection
		        if (
						geojson && 
						typeof geojson === 'object' && 
						geojson.type && 
						geojson.type == 'GeometryCollection' && 
						geojson.geometries && 
						geojson.geometries.length > 0
					) {
		            $("textarea#geojson").removeAttr("disabled");
		        } else {
		        	abort();
		        }
		    } catch (error) {
		        abort();
		    }	
        }
    });
	
	$('#entrySelector').select2({
		data: dropdown_data[1].children,
		width: 'element',
		height: 'element',
		placeholder: 'Choose Countries',
		allowClear: false,
	}).on('change', function(e) {
		updateAreaMap();
	});
	
	let country_url = "/media/data/countries_simplified.json";
	fetch(country_url)
		.then(function(resp) { return resp.json(); })
		.then(function(data) {
			countryGeoJSON = data;
		});

	$('a[data-bs-toggle="tab"]').on('shown.bs.tab', function(e) {
		
		console.log('shown.bs.tab',e);
		
		const target = $(e.target).attr("href") // activated tab
		const area_type = $(e.target).attr("ref") // activated tab
		map_clear();
		// feed area type to hidden input
		$("input[name='type']").val(area_type)
		console.log('tab id:', target);
		$drawControl.toggle(target !== '#areas_codes');
	});
})
.catch(error => console.error("An error occurred:", error));

function addDrawingControl() {
	
	draw = whg_map._draw;
	$drawControl = $(whg_map._drawControl);
		
	whg_map.on('draw.create', updateDraw); // draw events fail to register if not done individually
	whg_map.on('draw.delete', updateDraw);
	whg_map.on('draw.update', updateDraw);
	function updateDraw() {
		const featureCollection = draw.getAll();
		$("textarea#geojson").val(featureCollection.features.length > 0 ? JSON.stringify( geometryFeatureCollection(featureCollection) ) : '');
	}
}

function geometryFeatureCollection(featureCollection) {
	return {
	  "type": "GeometryCollection",
	  "geometries": featureCollection.features.map(feature => feature.geometry)
	};	
}

function featureGeometryCollection(geometryCollection) {
	if (!!geometryCollection.coordinates) { // First, convert any plain geometries to GeometryCollection
		geometryCollection = {
			"type": "GeometryCollection",
	  		"geometries": [geometryCollection]
		}
	}
	return {
      type: 'FeatureCollection',
      features: geometryCollection.geometries.map(geometry => {
        return {
          type: 'Feature',
          geometry: geometry,
          properties: {}
        };
      })
    };	
}

function map_clear() {
	draw.deleteAll();
	whg_map.clearSource('countries').clearSource('hulls').reset();
	if (action == "create") {
		$("textarea#geojson").val('');
	}
}

function updateAreaMap() {

	whg_map
	.clearSource('countries')
	.clearSource('hulls');
	$("textarea#geojson").val('');

	var data = $('#entrySelector').select2('data');
	let cbuffer = $("select#buffer_km").val();
	let hullCollection = whg_map.nullCollection();

	function fitMap(features) {
		try {
			whg_map.fitBounds(bbox(features), {
				padding: 30,
				maxZoom: 7,
				duration: 1000,
			});
		} catch {
			whg_map.reset();
		}
	}

	if (data.length > 0) {
		const selectedCountries = data.length < 1 || data.some(feature => feature.feature) ? [] : 
			(data.some(region => region.ccodes) ? [].concat(...data.map(region => region.ccodes)) : data.map(country => country.id));
		countryCache.filter(selectedCountries).then(filteredCountries => {
			filteredCountries.features.forEach((feature, index) => { 
				if (cbuffer > 0) {
					const bufferedHull = convex(buffer(feature, cbuffer, { units: 'kilometers' }));
	        		hullCollection.features.push(bufferedHull);
				} 
			});
			if (cbuffer > 0) {
				hullCollection = combine(dissolve(flatten(hullCollection)));
				whg_map.getSource('hulls').setData(hullCollection);
			}
			whg_map.getSource('countries').setData(filteredCountries);
			let primaryCollection = cbuffer > 0 ? hullCollection : filteredCountries;
			$("textarea#geojson").val(JSON.stringify( geometryFeatureCollection(primaryCollection) ) || '');
			fitMap(primaryCollection);
		});
	} else whg_map.reset();
}

/*
THE FOLLOWING FUNCTIONS ARE AS-YET REDUNDANT AND MIGHT EVENTUALLY BE REMOVED
 */

// ES query to count...retrieve?
function fetchCount(coords) {
	//startMapitSpinner()
	console.log('coords', coords)
	let context = {
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
	let tup = [o(ra() * s), o(ra() * s), o(ra() * s)]

	const rgbToHex = (r, g, b) => '#' + [r, g, b].map(x => {
		const hex = x.toString(16)
		return hex.length === 1 ? '0' + hex : hex
	}).join('')

	return rgbToHex(tup[0], tup[1], tup[2])
}

function zoomTo(id) {
	whg_map.setView(idToFeature[id]._latlng, whg_map.getZoom() + 2)
}

function cleanJson(text) {
	z = text.replace(/'/g, '\\"')
	y = z.replace(/point/, 'Point')
	return JSON.parse(JSON.parse(y))
}
