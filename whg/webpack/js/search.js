// /whg/webpack/search.js

import '/webpack/node_modules/@maptiler/sdk/dist/maptiler-sdk.umd.min.js';
import '/webpack/node_modules/@maptiler/sdk/dist/maptiler-sdk.css';
import datasetLayers from './mapLayerStyles';
import { bbox, centroid } from './6.5.0_turf.min.js';
import { attributionString } from './utilities';
import { CustomAttributionControl } from './customMapControls';
import '../css/search.css';

let results = null;
let checkboxStates = {};
let allTypes = [];
let allCountries = [];
let isInitialLoad = true;
let initialTypeCounts = {};
let initialCountryCounts = {};

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

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');
            const style = mappy.getStyle();
            style.layers.forEach(layer => {
                if (layer.id.includes('label')) {
                    mappy.setLayoutProperty(layer.id, 'visibility', 'none');
                }
            });
            
		    mappy.addSource('places', {
				'type': 'geojson',
				'data': {
				  "type": "FeatureCollection",
				  "features": []
				},
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(function(layer) {
				mappy.addLayer(layer);
			});
			
			mappy.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: mapParameters.controls.attribution.open === false,
			}), 'bottom-right');
			
			function getFeatureId(e) {
				const features = mappy.queryRenderedFeatures(e.point);
				if (features.length > 0) {
					const topFeature = features[0]; // Handle only the top-most feature
					const topLayerId = topFeature.layer.id;
					// Check if the top feature's layer id starts with the id of any layer in datasetLayers
					const isTopFeatureInDatasetLayer = datasetLayers.some(layer => topLayerId.startsWith(layer.id));
					if (isTopFeatureInDatasetLayer) {
						mappy.getCanvas().style.cursor = 'pointer';
				        return topFeature.id;
					}
				}
				mappy.getCanvas().style.cursor = 'grab';
		        return null;
			}
			
			mappy.on('mousemove', function(e) {
				getFeatureId(e);
			});
			
			mappy.on('click', function(e) {
				$('.result').eq(getFeatureId(e)).attr('data-map-clicked', 'true').click();
			});
            
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
        const storedResults = localStorage.getItem('last_results');
        results = storedResults ? JSON.parse(storedResults) : results;

        if (results) {
            renderResults(results);
            $("#result_facets").show();
        } else {
            console.log('no results');
            $("#adv_options").show();
        }

        $('#advanced_search').hide();

        $('#advanced_search-toggle').click(() => $('#advanced_search').slideToggle(300));

        $('#close-advanced_search').click(() => $('#advanced_search').slideUp(300));

        $("#a_search, #d_input input").on('click keypress', function(event) {
            if (event.type === 'click' || (event.type === 'keypress' && event.which === 13)) {
                event.preventDefault();
                initiateSearch();
            }
        });
    })
    .catch(error => console.error("An error occurred:", error));

// Filter results based on checked checkboxes
function filterResults(checkedTypes, checkedCountries) {
	let filteredResults = results.features.filter(function(feature) {
		let result = feature.properties
		return (checkedTypes.length === 0 || checkedTypes.some(type => result.types.includes(type))) &&
			(checkedCountries.length === 0 || checkedCountries.some(country => result.ccodes.includes(country)));
	});
	for (let i = 0; i < filteredResults.length; i++) {
	    filteredResults[i].id = i;
	}
	console.log('Filtering...', results, filteredResults);
	return {type: "FeatureCollection", features: filteredResults, query: results.query}
}

function getCheckedTypes() {
	let checkedTypes = $('.type-checkbox:checked').map(function() {
		return this.value;
	}).get();
	return checkedTypes
}

function getCheckedCountries() {
	let checkedCountries = $('.country-checkbox:checked').map(function() {
		return this.value;
	}).get();
	return checkedCountries
}

// render results and facet checkboxes
function renderResults(featureCollection) {
	console.log('results (global)', featureCollection)
	$("#adv_options").hide()
	$("#result_facets").show()
	$("#detail_box").show()
	$("#result_count").html(featureCollection.features.length)
	// Clear previous results
	$('#search_results').empty();

	mappy.getSource('places').setData(featureCollection);    

	// Select the search_results div
	const $resultsDiv = $('#search_results');

	// search term to search input
	$("#d_input input").val(!!featureCollection.query ? featureCollection.query : '');

	// Iterate over the results and append HTML for each
	// NB these are parents only
	// hit (delivers): [title, searchy, whg_id, pid, linkcount, variants,
	//    ccodes, fclasses, types, geoms]
	// hit (also): [uri, names, links, timespans, dataset]
	// TODO: Portal URL not yet implemented
	// link to portal: <a href="/places/${result.whg_id}/portal">portal</a>
	
	let results = featureCollection.features;
	results.forEach(feature => {
		
		let result = feature.properties;
		
		const count = parseInt(result.linkcount) + 1
		const html = `
            <div class="result">
                <p>${result.title} (${count} in set)
                  <span class="float-end">
                      <a href="/places/${result.whg_id}/portal" title="portal for ${ result.whg_id }">portal</a>
                  </span>
									</p>
            </div>
        `;
		$resultsDiv.append(html);

	});

	if (isInitialLoad) {
		// sets values of global variables
		allTypes = getAllTypes(results);
		allCountries = getAllCountries(results);
		isInitialLoad = false;

		// console.log('allTypes', allTypes)
		// console.log('allCountries', allCountries)
	}

	// checkboxes for types in intial results
	$('#type_checkboxes').empty().append('<p>Place Types</p>');
	allTypes.forEach(type => {
		const checkbox = $('<input>', {
			type: 'checkbox',
			id: 'type_' + type,
			value: type,
			class: 'filter-checkbox type-checkbox',
			checked: checkboxStates[type] || false
		});
		const count = initialTypeCounts[type] || 0;
		const label = $('<label>', {
			'for': 'type_' + type,
			text: `${type} (${count})`
		});
		$('#type_checkboxes').append(checkbox).append(label).append('<br>');
	});

	// checkboxes for countries in initial results
	$('#country_checkboxes').empty().append('<p>Countries</p>');
	allCountries.forEach(country => {
		const cName = ccode_hash[country]['gnlabel'];
		const checkbox = $('<input>', {
			type: 'checkbox',
			id: 'country_' + country,
			value: country,
			class: 'filter-checkbox country-checkbox',
			checked: checkboxStates[country] || false
		});
		const count = initialCountryCounts[country] || 0;
		const label = $('<label>', {
			'for': 'country_' +
				country,
			text: `${cName} (${country}; ${count})`
		});

		$('#country_checkboxes').append(checkbox).append(label).append('<br>');
	});

	$('.filter-checkbox').change(function() {
		// store state
		checkboxStates[this.value] = this.checked;
		console.log('checkboxStates', checkboxStates)

		// Get all checked checkboxes
		let checkedTypes = getCheckedTypes();
		let checkedCountries = getCheckedCountries();

		// Log the current selected types and countries for debugging
		// console.log('Selected Types:', checkedTypes);
		// console.log('Selected Countries:', checkedCountries);

		let filteredResults = filterResults(checkedTypes, checkedCountries);

		// Log the filtered results for debugging
		console.log('Filtered Results:', filteredResults);

		// Render the filtered results
		if (filteredResults.features.length > 0) {
			renderResults(filteredResults);
		} else {
			// Handle the case where there are no matching results
			$('#search_results').html('<p>No results match the selected filters.</p>');
			$('#detail').empty(); // Clear the detail view
		}
	});

	$('.result').click(function() {
		const index = $(this).index(); // Get index of clicked card
	
		mappy.removeFeatureState({ source: 'places' });	
		mappy.setFeatureState({ source: 'places', id: index }, { highlight: true });
	    
	    if ($(this).attr('data-map-clicked') === 'true') { // Scroll table
			$(this).removeAttr('data-map-clicked');
			const $container = $('#result_container');
			$container.scrollTop($(this).offset().top - $container.offset().top);
		}
		else if ($(this).attr('data-map-initialising') === 'true') {
			$(this).removeAttr('data-map-initialising');
			mappy.fitBounds(bbox(featureCollection), {
		        padding: 30,
		        // maxZoom: 5,
		        duration: 1000,
		    });
		}
		else {
		    mappy.flyTo({ // Adjust map
				center: centroid(featureCollection.features[index]).geometry.coordinates,
				duration: 1000,
		    });
		}
		
		renderDetail(results[index]); // Update detail view with clicked result data
		$('.result').removeClass('selected');
		$(this).addClass('selected');
	});
	
	
	
	if (featureCollection.features.length > 0) {
		// Highlight first result and render its detail
		$('.result').first().attr('data-map-initialising', 'true').click();
	}
	else {
	    mappy.flyTo({
			center: mapParameters.center,
			zoom: mapParameters.zoom,
	        speed: .5,
	    });
		$('#detail').empty(); // Clear the detail view
	}
}

function getAllTypes(results) {
	let typesSet = new Set();
	let typeCounts = {};

	results.forEach(feature => {
		let result = feature.properties;
		result.types.forEach(type => {
			typesSet.add(type);

			// Increment count for this type
			if (!typeCounts[type]) {
				typeCounts[type] = 0;
			}
			typeCounts[type]++;
		});
	});

	// Set the global variable for initial type counts
	initialTypeCounts = typeCounts;

	return Array.from(typesSet).sort();
}

function getAllCountries(results) {
	let countriesSet = new Set();
	let countryCounts = {};

	results.forEach(feature => {
		let result = feature.properties;
		result.ccodes.forEach(country => {
			countriesSet.add(country);

			// Increment count for this country
			if (!countryCounts[country]) {
				countryCounts[country] = 0;
			}
			countryCounts[country]++;
		});
	});

	// Set the global variable for initial country counts
	initialCountryCounts = countryCounts;

	return Array.from(countriesSet).sort();
}

function updateCheckboxCounts(features) {
	// Count the number of results for each type and country
	let typeCounts = {};
	let countryCounts = {};
	features.forEach(feature => {
		let result = feature.properties;
		result.types.forEach(type => {
			typeCounts[type] = (typeCounts[type] || 0) + 1;
		});
		result.ccodes.forEach(country => {
			countryCounts[country] = (countryCounts[country] || 0) + 1;
		});
	});

	// Update the checkbox labels with the counts
	$('.type-checkbox').each(function() {
		const type = this.value;
		$(`label[for='type_${type}']`).text(`${type} (${typeCounts[type] || 0})`);
	});
	$('.country-checkbox').each(function() {
		const country = this.value;
		const countryName = ccode_hash[country] ? ccode_hash[country]['gnlabel'] : country;
		$(`label[for='country_${country}']`).text(`${countryName} (${countryCounts[country] || 0})`);
	});
}

function suggestionsGeoJSON(suggestions) { // Convert ES suggestions to GeoJSON FeatureCollection
	let featureCollection = {
	  type: "FeatureCollection",
	  features: [],
	};
	let idCounter = 0;
	for (const itemSource of suggestions) {
	  let item = {... itemSource};
	  const feature = {
	    type: "Feature",
	    geometry: {
			type: "GeometryCollection",
        	geometries: item.geom
		},
	    properties: {},
	    id: idCounter,
	  };
	  delete item.geom;
	  for (const prop in item) { // Copy all non-standard properties from the original item
	    if (!["type", "geometry", "properties"].includes(prop)) {
	      feature.properties[prop] = item[prop];
	    }
	  }
	  featureCollection.features.push(feature);
	  idCounter++;
	}
	return featureCollection;
}

function initiateSearch() {
	isInitialLoad = true;

	localStorage.removeItem('last_results')

	const query = $('#search-input').val(); // Get the query from the input
	const options = gatherOptions(); //

	// AJAX GET request to SearchView() with the options (includes qstr)
	$.get("/search/index", options, function(data) {

		results = suggestionsGeoJSON(data['suggestions']); // Convert to GeoJSON and replace global variable
		results.query = query;
		localStorage.setItem('last_results', JSON.stringify(results));

		renderResults(results);

	});
}

function gatherOptions() {
	// gather and return option values from the UI
	let fclasses = [];
	$('#search_filters input:checked').each(function() {
		fclasses.push($(this).val());
	});
	let options = {
		"qstr": $('#d_input input').val(),
		"idx": "whg",
		"fclasses": fclasses.join(','),
		"start": $("#input_start").val(),
		"end": $("#input_end").val(),
		"bounds": $("#boundsobj").val()
	}
	return options;
}

function renderDetail(feature) {
	
	let result = feature.properties;
	let detailHtml = "";

	if (result.variants && result.variants.length > 0) {
		detailHtml += `<p>Variants: ${result.variants.join(', ')}</p>`;
	} else {
		detailHtml += `<p>No Variants Available</p>`; // Or you can just skip adding this line
	}

	if (result.ccodes && result.ccodes.length > 0) {
		detailHtml += `<p>Country Codes: ${result.ccodes.join(', ')}</p>`;
	} else {
		detailHtml += `<p>No Country Codes Available</p>`; // Or you can just skip adding this line
	}

	if (result.fclasses && result.fclasses.length > 0) {
		detailHtml += `<p>Feature Classes: ${result.fclasses.join(', ')}</p>`;
	} else {
		detailHtml += `<p>No Feature Classes Available</p>`; // Or you can just skip adding this line
	}

	if (result.types && result.types.length > 0) {
		detailHtml += `<p>Types: ${result.types.join(', ')}</p>`;
	} else {
		detailHtml += `<p>No Types Available</p>`; // Or you can just skip adding this line
	}

	$('#detail').html(detailHtml);

}
