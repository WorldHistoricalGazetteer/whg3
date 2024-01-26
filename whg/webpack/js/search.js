// /whg/webpack/search.js

import Dateline from './dateline';
import throttle from 'lodash/throttle';
import { geomsGeoJSON } from './utilities';
import { ccode_hash } from '../../../static/js/parents';
import { CountryCacheFeatureCollection } from  './countryCache';
import '../css/dateline.css';
import '../css/search.css';

let results = null;
let checkboxStates = {};
let allTypes = [];
let allCountries = [];
let isInitialLoad = true;
let initialTypeCounts = {};
let initialCountryCounts = {};
let draw;
let $drawControl;
let countryCache = new CountryCacheFeatureCollection();

let mapParameters = {
	maxZoom: 13,
    fullscreenControl: true,
    downloadMapControl: true,
    drawingControl: {hide: true},
    temporalControl: {
        fromValue: 800,
        toValue: 1800,
        minValue: -2000,
        maxValue: 2100,
        open: false,
        includeUndated: true, // null | false | true - 'false/true' determine state of select box input; 'null' excludes the button altogether
        epochs: null,
        automate: null,
    },
}
let mappy = new whg_maplibre.Map(mapParameters);

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
            
            mappy
            .newSource('countries')  // Add empty source
			.newLayerset('countries', 'countries', 'countries');
            
		    mappy
		    .newSource('places') // Add empty source
			.newLayerset('places');			
			
			function getFeatureId(e) {
				const features = mappy.queryRenderedFeatures(e.point);
				if (features.length > 0) {
					if (features[0].layer.id.startsWith('places_')) { // Query only the top-most feature
						mappy.getCanvas().style.cursor = 'pointer';
				        return features[0].id;
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
		
		draw = mappy._draw;
		$drawControl = $(mappy._drawControl);
		
		mappy.on('draw.create', initiateSearch); // draw events fail to register if not done individually
		mappy.on('draw.delete', initiateSearch);
		mappy.on('draw.update', initiateSearch);
		
		const dateRangeChanged = throttle(() => { // Uses imported lodash function
		    initiateSearch();
		}, 300); 
    
		updateSearchState(true); // Retrieve search options from LocalStorage

		if (!!mapParameters.temporalControl) {
			let datelineContainer = document.createElement('div');
			datelineContainer.id = 'dateline';
			document.querySelector('.maplibregl-control-container').appendChild(datelineContainer);
			window.dateline = new Dateline({
				...mapParameters.temporalControl,
				onChange: dateRangeChanged
			});
			$(window.dateline.button).on('click', initiateSearch);
		};
			
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
        
	    $('#search_input').on('keyup', function (event) {
			if(event.which === 13) {
				event.preventDefault();
	        	initiateSearch();
			}
	    });
        
	    $('#a_search').on('click', function () {
	        initiateSearch();
	    });
        
	    $('#a_clear').on('click', function () { // Clear the input, results, and map
	        $('#search_input').val('').focus();
			$('#search_results').empty();
	        mappy
	        .getSource('places')
	        .setData(mappy.nullCollection());
	        mappy.reset();
			localStorage.removeItem('last_results');
	    });
	    
        var suggestions = new Bloodhound({ // https://github.com/twitter/typeahead.js/blob/master/doc/bloodhound.md#remote
            datumTokenizer: Bloodhound.tokenizers.whitespace,
            queryTokenizer: Bloodhound.tokenizers.whitespace,
            local:  [],
            indexRemote: true,
            remote: { // Returns simple array, like ["Glasgow","Glasgo"]
                url: '/search/suggestions/?q=%QUERY',
                wildcard: '%QUERY',
                rateLimitBy: 'debounce',
        		rateLimitWait: 100
            }
        });
        
        function wildcardMatcher(item, query) { // Need to use same filter as is used in Elastic search, because previous results are being kept with the `indexRemote` option
		    var wildcardRegex = new RegExp('.*' + Bloodhound.tokenizers.whitespace(query).join('.*') + '.*', 'i');
		    return wildcardRegex.test(item);
		}
		
		$("#search_input").typeahead( // Bootstrap3 version: https://github.com/bassjobsen/Bootstrap-3-Typeahead/blob/master/README.md
			{
				items: 20,
				source: suggestions.ttAdapter(),
				matcher: wildcardMatcher,
		  		afterSelect: function(title) {
					console.log('selected', title);
					initiateSearch();  
				}
			}
		);
		
		$("#filter_spatial #input_area").typeahead(
			{
				source: [...dropdown_data[0].children, ...dropdown_data[1].children], // Concatenate regions and countries
				displayText: item => item.text,
				autoSelect: true,
		  		afterSelect: function(item) {
					const countries = item.ccodes || [item.id];
			        countryCache.filter(countries).then(filteredCountries => {
			            mappy.getSource('countries').setData(filteredCountries);
			            try {
			                mappy.fitBounds(bbox(filteredCountries), {
			                    padding: 30,
			                    maxZoom: 7,
			                    duration: 1000,
			                });
			            } catch {
			                mappy.reset();
			            }
			        });	
				}
			}
		);

		// START Ids to session (kg 2023-10-31)
		function getCookie(name) {
		  let cookieValue = null;
		  if (document.cookie && document.cookie !== '') {
			const cookies = document.cookie.split(';');
			for (let i = 0; i < cookies.length; i++) {
			  const cookie = cookies[i].trim();
			  if (cookie.substring(0, name.length + 1) === (name + '=')) {
				cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
				break;
			  }
			}
		  }
		  return cookieValue;
		}

		// $('.portal-link').click(function(e) {
		$(document).on('click', '.portal-link', function(e) {
		// $('.result').on('click', '.portal-link', function(e) {
			e.preventDefault();
			e.stopPropagation();

			const pid = $(this).data('pid');
			const children= $(this).data('children') ?
				decodeURIComponent($(this).data('children')).split(',').map(id => parseInt(id, 10)) : [];
			const placeIds = [pid, ...children].filter(id => !isNaN(id) && id !== null && id !== undefined);
			const csrfToken = getCookie('csrftoken');

			console.log('pid', pid)
			console.log('children', $(this).attr('data-children'))
			console.log('placeIds', placeIds)
			console.log('csrfToken', csrfToken)

			$.ajax({
			  url: '/places/set-current-result/',
			  type: 'POST',
			  data: {
				'place_ids': placeIds,
				'csrfmiddlewaretoken': csrfToken
			  },
			  traditional: true,
			  success: function(response) {
				window.location.href = '/places/portal/';
			  },
			  error: function(xhr, status, error) {
				console.error("AJAX POST error:", error);
			  }
			});

		});
		// END Ids to session
    })
    .catch(error => console.error("An error occurred:", error));

// $(window).resize(function() {
//   if ($('#result_facets').height() > someValue) { // Replace someValue with the maximum height you want for #result_facets
//     $('#detail').collapse('hide');
//   } else {
//     $('#detail').collapse('show');
//   }
// }).resize(); // Trigger the resize event initially

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
	// $("#detail_box").show()
	// $("#result_count").html(featureCollection.features.length)
	// Clear previous results
	$('#search_results').empty();

	mappy.getSource('places').setData(featureCollection);    

	// Select the search_results div
	const $resultsDiv = $('#search_results');

	// search term to search input
	$("#d_input input").val(!!featureCollection.query ? featureCollection.query : '');

	// Iterate over the results and append HTML for each
	let results = featureCollection.features;
	
	$drawControl.toggle(results.length > 0 || draw.getAll().features.length > 0); // Leave control to allow deletion of areas
	results.forEach(feature => {
		let result = feature.properties;
		const count = parseInt(result.linkcount) + 1;
		const pid = result.pid;
		const children = result.children;
		// Encode children as a comma-separated string
		const encodedChildren = encodeURIComponent(children.join(','));

		// _index property
		let resultIdx = result.index.startsWith('whg') ? 'whg' : 'pub';

		// Add a class and a text descriptor based on the result type
		let html = `
            <div class="result ${resultIdx}-result">
                <p><span class="red-head">${result.title}</span> 
                  (${resultIdx === 'pub' ? 'unlinked record' : (count > 1 ? `${count} linked index records <i class="fas fa-link"></i>` : 'unlinked index record')})
                  <span class="float-end">
					<a href="#" class="portal-link"	data-pid="${pid}" 
						data-children="${encodedChildren}">${resultIdx === 'whg' ? 'place portal' : 'place detail'}
					</a>
					<!--<span class="result-idx">${resultIdx}</span>-->
                  </span>`;

		// if (children.length > 0) {
		// 	html += `<span class="ml-2">children: ${children.join(', ')}</span>`;
		// };
		html += `</p>`
		if (result.types && result.types.length > 0) {
			html += `<p>Type(s): ${result.types.join(', ')}</p>`;
		}

		if (result.variants && result.variants.length > 0) {
		  const threshold = 12;
		  const limitedVariants = result.variants.slice(0, threshold).join(', ');
		  const allVariants = result.variants.join(', ');

		  html += '<p>Variants ('+result.variants.length+'): ';
		  if (result.variants.length > threshold) {
			html += `<a href="#" id="variantsToggle" class="ms-2 italic">view all</a><br/>`;
		  }
		  html += `<span id="limitedVariants">${limitedVariants}</span>`;
		  if (result.variants.length > threshold) {
			html += `<span id="allVariants" style="display:none">${allVariants}</span>`;
		  }
		  html += '</p>';

		  // add listener
		  setTimeout(() => {
			const variantsToggleLink = document.getElementById('variantsToggle');
			if (variantsToggleLink) {
			  variantsToggleLink.addEventListener('click', toggleVariants);
			} else {
			  console.log('variantsToggle link not found');
			}
		  }, 0)
		} else {
			html += `<p> Variants: none provided</p>`; // Or you can just skip adding this line
		}

		$resultsDiv.append(html);

	});

	if (isInitialLoad) {
		// sets values of global variables
		allTypes = getAllTypes(results);
		allCountries = getAllCountries(results);
		isInitialLoad = false;
	}

	// checkboxes for types in initial results
	// $('#type_checkboxes').empty().append('<p>Place Types</p>');
	$('#type_checkboxes').empty();
	allTypes.forEach(type => {
		const checkbox = $('<input>', {
			type: 'checkbox',
			id: 'type_' + type.replace(' ','_'),
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
	// $('#country_checkboxes').empty().append('<p>Countries</p>');
	$('#country_checkboxes').empty();
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

	$('#typesCount').text(`(${allTypes.length})`);
	$('#countriesCount').text(`(${allCountries.length})`);

	// var chevronIcon = $('#headingCountries .accordion-toggle-indicator i');

	// 5 or fewer countries? open accordion; more? close it
	if (allCountries.length <= 5) {
		$('#collapseCountries').addClass('show').removeClass('collapse');
		$('#headingCountries .accordion-button').removeClass('collapsed').attr('aria-expanded', 'true');
		$("#headingCountries button .accordion-toggle-indicator").hide();
	} else {
		$('#collapseCountries').removeClass('show').addClass('collapse');
		$('#headingCountries .accordion-button').addClass('collapsed').attr('aria-expanded', 'false');
		$("#headingCountries button .accordion-toggle-indicator").show();
	}

	$('#collapseTypes').on('show.bs.collapse', function () {
		$('#headingTypes .accordion-toggle-indicator').html('<i class="info-collapse fas fa-chevron-up"></i>');
	}).on('hide.bs.collapse', function () {
		$('#headingTypes .accordion-toggle-indicator').html('<i class="info-collapse fas fa-chevron-down"></i>');
	});

	$('#collapseCountries').on('show.bs.collapse', function () {
		$('#headingCountries .accordion-toggle-indicator').html('<i class="info-collapse fas fa-chevron-up"></i>');
	}).on('hide.bs.collapse', function () {
		$('#headingCountries .accordion-toggle-indicator').html('<i class="info-collapse fas fa-chevron-down"></i>');
	});
	$('.accordion-button').on('click', function() {
		var indicator = $(this).find('.accordion-toggle-indicator');
		if ($(this).hasClass('collapsed')) {
			indicator.html('<i class="info-collapse fas fa-chevron-down');
		} else {
			indicator.html('<i class="info-collapse fas fa-chevron-up');
		}
	});


	$('.filter-checkbox').change(function() {
		// store state
		checkboxStates[this.value] = this.checked;
		console.log('checkboxStates', checkboxStates);
		if (!programmaticChange) {
			updateSearchState();
		}

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
		
		// renderDetail(results[index]); // Update detail view with clicked result data
		$('.result').removeClass('selected');
		$(this).addClass('selected');
	});
	

	if (featureCollection.features.length > 0) {
		// Highlight first result and render its detail
		$('.result').first().attr('data-map-initialising', 'true').click();
	}
	else {
	    mappy.reset();
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

let programmaticChange = false;
function updateSearchState(retrieve=false, results=false) {
	// search_input, checkboxes, temporal filter, spatial filter, results
	if (retrieve) {
		const searchStateJSON = localStorage.getItem('search_state');
		if (searchStateJSON) {
			programmaticChange = true;
			const searchState = JSON.parse(searchStateJSON);
			$('#search_input').val(searchState['search_input']);
			$('#result_facets input[type="checkbox"]').prop('checked', false);
	        searchState['checkedboxes'].forEach(function(id) {
		    	$('#' + id).prop('checked', true);
		    });
		    mapParameters.temporalControl = searchState['temporal_filter'];
			draw.add(searchState['spatial_filter']);
			programmaticChange = false;
		}
	}
	else {
		let searchState = {}
		searchState['search_input'] = $('#search_input').val();
		searchState['checkedboxes'] = $('#result_facets input[type="checkbox"]:checked')
			.map(function() {
				return this.id;
			})
			.get();
			
		if (results) {
			console.log('updateSearchState results', results);
			searchState['temporal_filter'] = {
				'fromValue': dateline.fromValue,
				'toValue': dateline.toValue,
				'minValue': dateline.minValue,
				'maxValue': dateline.maxValue,
				'open': dateline.open,
				'includeUndated': dateline.includeUndated,
				'epochs': dateline.epochs,
				'automate': dateline.automate			
			};
			searchState['spatial_filter'] = draw.getAll();
			searchState['suggestions'] = results.suggestions;
		}
			
		localStorage.setItem('search_state', JSON.stringify(searchState));
	}	
}

function initiateSearch() {
	
	if (programmaticChange) return; // initiateSearch has been triggered by initialisation of filters
	
	isInitialLoad = true;
	localStorage.removeItem('last_results')

	const query = $('#search_input').val(); // Get the query from the input
	const options = gatherOptions(); //
	console.log('initiateSearch()', query, options)

/*	// AJAX GET request to SearchView() with the options (includes qstr)
	$.get("/search/index", options, function(data) {

		results = geomsGeoJSON(data['suggestions']); // Convert to GeoJSON and replace global variable
		results.query = query;
		localStorage.setItem('last_results', JSON.stringify(results));
		updateSearchState();
		renderResults(results);

	});*/

  	// AJAX POST request to SearchView() with the options (includes qstr)
    $.ajax({
        type: 'POST',
        url: '/search/index/',
	    data: JSON.stringify(options),
	    contentType: 'application/json',
        headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },  // Include CSRF token in headers for Django POST requests
        success: function(data) {
            results = geomsGeoJSON(data['suggestions']);
            results.query = query;
            localStorage.setItem('last_results', JSON.stringify(results));
            updateSearchState(false, data);
            renderResults(results);
        },
        error: function(error) {
            console.error('Error:', error);
        }
    });
}

function gatherOptions() {
	// gather and return option values from the UI
	let fclasses = [];
	// the whg index, for dev or prod according to local_settings
	var eswhg = "{{ es_whg|escapejs }}";
	$('#search_filters input:checked').each(function() {
		fclasses.push($(this).val());
	});
	
	let area_filter = {
	  "type": "GeometryCollection",
	  "geometries": draw.getAll().features.map(feature => feature.geometry)
	}
	
	let options = {
		"qstr": $('#d_input input').val(),
		"idx": eswhg,
		"fclasses": fclasses.join(','),
		"start": window.dateline.open ? window.dateline.fromValue : '', 
		"end": window.dateline.open ? window.dateline.toValue : '',
		"undated": window.dateline.open ? window.dateline.includeUndated : true,
		"bounds": area_filter
	}
	return options;
}

// variant list can grow too long
function toggleVariants(event) {
	console.log('toggleVariants called');
    event.preventDefault();
    const fullListDiv = document.getElementById('allVariants');
    const limitedListDiv = document.getElementById('limitedVariants');
    const moreLink = event.target;

    if (fullListDiv.style.display === 'none') {
        fullListDiv.style.display = 'block';
        limitedListDiv.style.display = 'none';
        moreLink.innerHTML = 'view fewer';
    } else {
        fullListDiv.style.display = 'none';
        limitedListDiv.style.display = 'block';
        moreLink.innerHTML = 'view all';
    }
}

// function renderDetail(feature) {
// 	let result = feature.properties;
// 	let detailHtml = "";
//
// 	detailHtml += `<h5>${result.title}</h5>`
//
// 	if (result.variants && result.variants.length > 0) {
// 		const threshold = 5;
// 		const limitedVariants = result.variants.slice(0, threshold).join(', ');
// 		const allVariants = result.variants.join(', ');
//
// 		detailHtml += '<p>Variants: ';
//         if (result.variants.length > threshold) {
//             detailHtml += `<a href="#" id="variantsToggle" class="ms-2 italic">view all</a><br/>`;
//         }
// 		detailHtml += `<span id="limitedVariants">${limitedVariants}</span>`;
// 		if (result.variants && result.variants.length > threshold) {
// 			detailHtml += `<span id="allVariants" style="display:none">${allVariants}</span>`;
// 		}
// 		detailHtml += '</p>';
//
// 		// add listener
// 		setTimeout(() => {
// 			const variantsToggleLink = document.getElementById('variantsToggle');
// 			if (variantsToggleLink) {
// 				// console.log('Attaching event listener to variantsToggle');
// 				variantsToggleLink.addEventListener('click', toggleVariants);
// 			} else {
// 				console.log('variantsToggle link not found');
// 			}
// 		}, 0)
//
// 	} else {
// 		detailHtml += `<p>No Variants Available</p>`; // Or you can just skip adding this line
// 	}
//
// 	if (result.ccodes && result.ccodes.length > 0) {
// 		detailHtml += `<p>Country Codes: ${result.ccodes.join(', ')}</p>`;
// 	} else {
// 		detailHtml += `<p>No Country Codes Available</p>`; // Or you can just skip adding this line
// 	}
//
// 	if (result.fclasses && result.fclasses.length > 0) {
// 		detailHtml += `<p>Feature Classes: ${result.fclasses.join(', ')}</p>`;
// 	} else {
// 		detailHtml += `<p>No Feature Classes Available</p>`; // Or you can just skip adding this line
// 	}
//
// 	if (result.types && result.types.length > 0) {
// 		detailHtml += `<p>Types: ${result.types.join(', ')}</p>`;
// 	} else {
// 		detailHtml += `<p>No Types Available</p>`; // Or you can just skip adding this line
// 	}
//
// 	$('#detail').html(detailHtml);
//
// }
