// /whg/webpack/portal.js

import throttle from 'lodash/throttle';
import { attributionString, deepCopy, geomsGeoJSON } from './utilities';
import Historygram from './historygram';
import { popupFeatureHTML } from './getPlace.js';
import { init_collection_listeners } from './collections.js';
import { add_to_collection } from './collections.js';

import '../css/mapAndTableMirrored.css';
import '../css/dateline.css';
import '../css/portal.css';

const payload = JSON.parse($('#payload_data').text());

let checked_cards = [];

let mapParameters = {
    zoom: 4, // Required initially to retrieve ecoregion data from the rendered layers
    center: centroid,
	maxZoom: 17,
    style: [
		'WHG',
		'Satellite'
	],
/*    basemap: ['natural-earth-1-landcover', 'natural-earth-2-landcover', 'natural-earth-hypsometric-noshade'],
    basemap: 'natural-earth-2-landcover',*/
    terrainControl: true,
	temporalControl: true
}
const defaultZoom = 8;
let mappy = new whg_maplibre.Map(mapParameters);

const noSources = $('<div>').html('<i>None - please adjust time slider.</i>').hide();

let featureCollection;
let relatedFeatureCollection;
let nearbyFeatureCollection;
let showingRelated = false;

let nearPlacePopup = new whg_maplibre.Popup({
	closeButton: false,
	})
.addTo(mappy);
$(nearPlacePopup.getElement()).hide();

function waitMapLoad() {
    return new Promise((resolve) => {
        mappy.on('load', () => {
            console.log('Map loaded.');

            mappy
			.newSource('nearbyPlaces') // Add empty source
			.newLayerset('nearbyPlaces', 'nearbyPlaces', 'nearby-places');

            mappy
			.newSource('places') // Add empty source
			.newLayerset('places')
			.addFilter(['!=', 'outOfDateRange', true]);

			const dateRangeChanged = throttle((fromValue, toValue, includeUndated) => { // Uses imported lodash function
			    filterSources(fromValue, toValue, includeUndated);
			}, 300);

			if (!!mapParameters.temporalControl) {
				new Historygram(mappy, allts, dateRangeChanged);
			};

			mappy.on('mousemove', function(e) {
				const features = mappy.queryRenderedFeatures(e.point);

				function clearHighlights() {
					if (mappy.highlights.length > 0) {
						mappy.getCanvas().style.cursor = 'grab';
						mappy.clearHighlights();
						$('.source-box').removeClass('highlight');
					}
				}

				if (!showingRelated) {
					if (features.length > 0) {
						clearHighlights();
						features.forEach(feature => {
							if (feature.layer.id.startsWith('places_')) {
								mappy.highlight(feature);
								$('.source-box').eq(feature.id).addClass('highlight');
							}
						});
						features.forEach(feature => { // Check nearbyPlaces
							if (feature.layer.id.startsWith('nearbyPlaces_')) {
								nearPlacePopup
								.setLngLat(e.lngLat)
								.setHTML(popupFeatureHTML(feature, false)); // second parameter indicates clickability								
							}
						$(nearPlacePopup.getElement()).show();
						});
						if (mappy.highlights.length > 0) {
							mappy.getCanvas().style.cursor = 'pointer';
						}

					} else {
						clearHighlights();
						$(nearPlacePopup.getElement()).hide();
					}
				}

			});

			mappy.on('click', function() {
				if (!showingRelated && mappy.highlights.length > 0) {
					console.log(mappy.highlights);
					mappy.fitViewport( bbox( geomsGeoJSON(mappy.highlights) ) );
				}
			});
			
			const ecoFeatures = mappy.queryRenderedFeatures(mappy.project(centroid)).filter(feature => {
			    return feature.source === 'ecoregions';
			});
			ecoFeatures.forEach(feature => {
		        if (feature.layer['source-layer'] === 'biomes') {
		            geoData.biome.name = feature.properties.label;
		            geoData.biome.url = `https://en.wikipedia.org/wiki/${feature.properties.label.charAt(0) + feature.properties.label.slice(1).toLowerCase().replace('&','and').replace(' ','_')}`;
		        } else if (feature.layer['source-layer'] === 'ecoregions') {
		            geoData.ecoregion.name = feature.properties.label;
		            geoData.ecoregion.url = `https://en.wikipedia.org/wiki/${feature.properties.label.charAt(0) + feature.properties.label.slice(1).toLowerCase().replace('&','and').replace(' ','_')}`;
		        }
			});

			mappy.getContainer().style.opacity = 1;

            resolve();
        });
    });
}

function waitDocumentReady() {
    return new Promise((resolve) => {
        $(document).ready(() => {
            // Get the 'add to collection' link and the 'addtocoll_popup' div
            const link = document.getElementById('addchecked');
            const popup = document.getElementById('addtocoll_popup');

			let checked_cards =[]

			document.querySelectorAll('input[name="r_anno"]').forEach(radio => {
					radio.addEventListener('click', function() {
							// Add the data-id value of the radio input to the checked_cards array
							const pid = $(this).data('id');
							checked_cards = [pid];
							console.log('checked_cards', checked_cards);
							// Unhide the #addtocoll span
							document.getElementById('addtocoll').style.display = 'block';
					});
			});
			
		    // Initialize modal dialog
		    $("#addtocoll_popup").dialog({
		        autoOpen: false,
		        modal: true,
		        width: 500,
		        title: "Add Place to a Collection",
		        buttons: {
		            "Close": function() {
		                $(this).dialog("close"); // Close dialog when "Close" button is clicked
		            }
		        }
		    });

		    // Show modal dialog when needed
		    $("#addchecked").click(function() {
		        $("#addtocoll_popup").dialog("open");
		    });

			// Add an event listener for the .a_addtocoll links
			document.querySelectorAll('.a_addtocoll').forEach(link => {
				link.addEventListener('click', function(event) {
					event.preventDefault();

					// Call the add_to_collection function with the appropriate arguments
					const coll = this.getAttribute('ref');
					add_to_collection(coll, checked_cards);

					// Clear the checked_cards array
					checked_cards = [];
				});
			});
            resolve();
        });
    });
}

Promise.all([waitMapLoad(), waitDocumentReady()])
    .then(() => {
		
		const allTimespans = payload.flatMap(place => place.timespans);
		const { earliestStartYear, latestEndYear } = allTimespans.reduce((acc, timespan) => {
		    const [startYear, endYear] = timespan;
		    return {
		        earliestStartYear: Math.min(acc.earliestStartYear, startYear),
		        latestEndYear: Math.max(acc.latestEndYear, endYear)
		    };
		}, { earliestStartYear: Infinity, latestEndYear: -Infinity });
		
		const temporalRange = Number.isFinite(earliestStartYear) && Number.isFinite(latestEndYear) 
			? `, and a temporal extent of <b>${Math.abs(earliestStartYear)}${earliestStartYear < 0 ? 'B' : ''}CE to ${Math.abs(latestEndYear)}${latestEndYear < 0 ? 'B' : ''}CE</b>` 
			: '';
			
		const allNameVariants = payload.flatMap(place => place.names.map(label => label.label));
		const distinctNameVariants = new Set(allNameVariants);

		const allTypes = payload.flatMap(place => place.types.map(type => type.label));
		const distinctTypes = new Set(allTypes);
		const distinctTypesArray = [...distinctTypes].sort();
        const distinctTypesText = distinctTypesArray.length > 0 ? 
        	`  as having type${distinctTypesArray.length > 1 ? 's' : ''} ${distinctTypesArray.map((name, index) => index < distinctTypesArray.length - 1 ? `<b>${name}</b>, ` : `<b>${name}</b>`).join('').replace(/,([^,]*)$/, `${distinctTypesArray.length == 2 ? '' : ','} and$1`)}` 
        	: '';
		
		$('#gloss').append($('<p>').addClass('mb-1').html(`
			This place is attested (so far) in the <b>${payload.length}</b> source${payload.length > 1 ? 's' : ''} listed below${distinctTypesText}, 
			with <b>${distinctNameVariants.size}</b> distinct name variant${distinctNameVariants.size > 1 ? 's' : ''}${temporalRange}.
		`));
		
		const elevationString = geoData.elevation ?
			` at an elevation of <b>${geoData.elevation}m</b>`
			: '';
        const adminString = geoData.admin.length > 0 ? 
        	` within the modern political boundaries of ${geoData.admin.map((name, index) => index < geoData.admin.length - 1 ? `<b>${name}</b>, ` : `<b>${name}</b>`).join('').replace(/,([^,]*)$/, `${geoData.admin.length == 2 ? '' : ','} and$1`)}, and` 
        	: '';
		$('<p>').addClass('mb-1').html(`
		    It lies${elevationString}${adminString} within the <a href="${geoData.ecoregion.url} target="_blank">${geoData.ecoregion.name}</a> ecoregion and <a href="${geoData.biome.url}" target="_blank">${geoData.biome.name}</a> biome.
		`).insertAfter($('#gloss').find('p:first'));

    	const collectionList = $('#collection_list');
    	const ul = $('<ul>').addClass('coll-list');
    	
    	$('#sources').find('h6').text(`${payload.length} Source${payload.length > 1 ? 's' : ''}`);

		payload.forEach(place => { // Reverse-sort each set of timespans by end year
		    place.timespans.sort((a, b) => b[1] - a[1]);
		});
		
		payload.sort((a, b) => { // Sort places based on the latest end year
		    const endYearA = a.timespans.length > 0 ? a.timespans[0][1] : Number.NEGATIVE_INFINITY;
		    const endYearB = b.timespans.length > 0 ? b.timespans[0][1] : Number.NEGATIVE_INFINITY;
		    return endYearB - endYearA;
		});

    	payload.forEach(place => {
			
			const moreNames = place.names.length > 10 ? `<div class="moreContent hidden">; ${place.names.slice(10).map(label => label.label).join('; ')}</div> [<a href="#" title="show more" class="more-link"><span><i class="fas fa-plus"></i></span><span class="hidden"><i class="fas fa-minus"></i></span></a>]` : '';
			
	        const sourceHTML = `
	            in: <a class="pop-link pop-dataset"
	                   data-id="${place.dataset.id}" data-toggle="popover"
	                   title="Dataset Profile" data-content="" tabindex="0" rel="clickover">
	                ${place.dataset.name.replace('(stub) ', '').substring(0, 25)}
	            </a>
				<div class="name-variants">
				    <strong class="larger">${place.title}</strong> ${place.names.slice(0, 10).map(label => label.label).join('; ') + moreNames}
				</div>
	            ${place.types.length > 0 ? `<div>Type${place.types.length > 1 ? 's' : ''}: ${place.types.map(type => type.label).join(', ')}</div>` : ''}
    			${place.timespans.length > 0 ? `<div>Chronology: ${place.timespans.reverse().map(timespan => timespan.join('-')).join(', ')}</div>` : ''}
	        `;
	        
	        $('#sources').append($('<div>').addClass('source-box').html(sourceHTML));		
			
		  	if (place.collections.length > 0) {
				place.collections.forEach(collection => {
					console.log('collection', collection);
					let listItem = '';
					// TODO: places are only ever in place collections
					if (collection.class === 'place') {
						listItem = `
							<a href="${ collection.url }" target="_blank"><b>${ collection.title.trim() } <i class="fas fa-external-link"></i></b>
							</a>, <br/>a collection of <sr>${ collection.count }</sr> places${!!collection.owner ? ` by ${collection.owner.name}` : ''}.
							<span class="showing"><p>${ collection.description }</p></span>
							[<a href="javascript:void(0);" data-id="${ collection.id }" class="show-collection"><span>preview</span><span class="showing">close</span></a>]
						`;
					} else {
						listItem = `
							<a href="${ collection.url }" target="_blank"><b>${title}</b>
							</a>, a collection of all <sr>${ collection.count }</sr> places in datasets
						`;
					}
					ul.append($('<li>').html(listItem));
				});
			}
		});
		
		const collectionCount = ul.find('li').length;
		if (collectionCount > 0) {
    		collectionList.prev('h6').text(`In ${collectionCount} Collection${collectionCount > 1 ? 's' : ''}`);
		    collectionList.append(ul);
		    
			switch (collectionCount) {
			    case 0:
			        $('#gloss').append(`It does not yet appear in any WHG collections.`);
			        break;
			    case 1:
			        $('#gloss').append(`It appears in the WHG collection shown below.`);
			        break;
			    default:
			        $('#gloss').append(`It appears in the ${collectionCount} WHG collections listed below.`);
			}
		    
		}
		else {
			$('#source_detail').hide();
		}

		$('#sources').append(noSources);
		
	    $('.more-link').click(function(event) {
	        event.preventDefault();
    		event.stopPropagation();
	        $(this).prev('.moreContent').toggleClass('hidden');
	        $(this).find('span').toggleClass('hidden');
	        const title = $(this).attr('title') === 'show more' ? 'show fewer' : 'show more';
    		$(this).attr('title', title);
	    });

		featureCollection = geomsGeoJSON(payload);
		console.log(featureCollection);
		mappy.getSource('places').setData(featureCollection);
		// Do not use fitBounds or flyTo due to padding bug in MapLibre/Maptiler
		mappy.fitViewport( bbox(featureCollection), defaultZoom );

	  	$('.source-box')
	  	.on('mousemove', function() {
			  if (!showingRelated) {
				  $(this)
				  .prop('title', 'Click to zoom on map.')
				  .addClass('highlight');
				  const index = $(this).index() - 1;
				  mappy.setFeatureState({source: 'places', id: index}, { highlight: true });
			  }
		})
	  	.on('mouseleave', function() {
			  if (!showingRelated) {
				  $(this)
				  .prop('title', '')
				  .removeClass('highlight');
				  const index = $(this).index() - 1;
				  mappy.setFeatureState({source: 'places', id: index}, { highlight: false });
				  mappy.fitViewport( bbox( featureCollection ), defaultZoom );
			  }
		})
	  	.on('click', function() {
			  if (!showingRelated) {
				  $(this)
				  .prop('title', '')
				  const index = $(this).index() - 1;
				  mappy.fitViewport( bbox( featureCollection.features[index].geometry ) );
			  }
		})

	  	// Show/Hide related Collection
	  	$(".show-collection").click(function(e) {
	  		e.preventDefault();
	  		const parentItem = $(this).parent('li');
	  		parentItem.toggleClass('showing');
	  		if (parentItem.hasClass('showing')) {
			  	$.get("/search/collgeom", {
			  			coll_id: $(this).data('id')
			  		},
			  		function(collgeom) {
						relatedFeatureCollection = collgeom;
			  			console.log('coll_places', relatedFeatureCollection);
						mappy.getSource('places').setData(relatedFeatureCollection);
						mappy.fitViewport( bbox(relatedFeatureCollection), defaultZoom );
			  		});
			  	showingRelated = true;
			}
			else {
				mappy.getSource('places').setData(featureCollection);
				mappy.fitViewport( bbox(featureCollection), defaultZoom );
				showingRelated = false;
			}
	  	})

        document.querySelectorAll('.toggle-link').forEach(link => {
            link.addEventListener('click', function(event) {
                toggleVariants(event, this);
            });
        });
                
        $('body').on('change', '#nearby_places, #radiusSelect', function() {
		    nearbyPlaces();
		});        
        $('body').on('click', '#update_nearby', function() {
		    nearbyPlaces();
		});

		new ClipboardJS('#permalinkButton', {
		    text: function() {
		      return window.location.href;
		    }
	  	})
		.on('success', function(e) {
		    e.clearSelection();
		    const tooltip = bootstrap.Tooltip.getInstance(e.trigger);
		    tooltip.setContent({ '.tooltip-inner': 'Permalink copied to clipboard successfully!' });
		    console.log('tooltip',tooltip);
		    setTimeout(function() { // Hide the tooltip after 2 seconds
		        tooltip.hide();
		    	tooltip.setContent({ '.tooltip-inner': tooltip._config.title }) // Restore original text
		    }, 2000);
		})
		.on('error', function(e) {
		    console.error('Failed to copy:', e.trigger);
		});
        
    })
    .catch(error => console.error("An error occurred:", error));

function filterSources(fromValue, toValue, includeUndated) {
	console.log(`Filter dates: ${fromValue} - ${toValue} (includeUndated: ${includeUndated})`);
	function inDateRange(source) {
        const timespans = source.timespans;
        if (timespans.length > 0) {
		    return !timespans.every(timespan => {
		        return timespan[1] < fromValue || timespan[0] > toValue;
		    });
        } else {
            return includeUndated;
        }
    }
	featureCollection.features.forEach((feature, index) => {
		const outOfDateRange = !inDateRange(feature.properties)
		feature.properties['outOfDateRange'] = outOfDateRange;
		$('.source-box').eq(index).toggle(!outOfDateRange);
	});
	mappy.getSource('places').setData(featureCollection);
	noSources.toggle($('.source-box:visible').length == 0);
}

/*function filterSources() {
	console.log(`Filter dates: ${window.dateline.fromValue} - ${window.dateline.toValue} (includeUndated: ${window.dateline.includeUndated})`);
	function inDateRange(source) {
		if (!window.dateline.open) return true;
        const timespans = source.timespans;
        if (timespans.length > 0) {
		    return !timespans.every(timespan => {
		        return timespan[1] < window.dateline.fromValue || timespan[0] > window.dateline.toValue;
		    });
        } else {
            return window.dateline.includeUndated;
        }
    }
	featureCollection.features.forEach((feature, index) => {
		const outOfDateRange = !inDateRange(feature.properties)
		feature.properties['outOfDateRange'] = outOfDateRange;
		$('.source-box').eq(index).toggle(!outOfDateRange);
	});
	mappy.getSource('places').setData(featureCollection);
	noSources.toggle($('.source-box:visible').length == 0);
}*/

function nearbyPlaces() {
	console.log('nearbyPlaces');
	
	if ( $('#nearby_places').prop('checked') ) {
        const center = mappy.getCenter();
        const radius = $('#radiusSelect').val();
        const lon = center.lng;
        const lat = center.lat;
        $('#update_nearby').show();

        fetch(`/api/spatial/?type=nearby&lon=${lon}&lat=${lat}&km=${radius}`)
            .then((response) => {
                if (!response.ok) {
                    throw new Error('Failed to fetch nearby places.');
                }
                return response.json(); // Parse the response JSON
            })
            .then((data) => {
				data.features.forEach((feature, index) => feature.id = index);
                nearbyFeatureCollection = data; // Set the global variable
                console.log(nearbyFeatureCollection);
                mappy.getSource('nearbyPlaces').setData(nearbyFeatureCollection);
				$('#update_nearby span').html(`${nearbyFeatureCollection.features.length}`);
				if (!showingRelated && nearbyFeatureCollection.features.length > 0) {
					mappy.fitViewport( bbox( nearbyFeatureCollection ), defaultZoom );
				}
            })
            .catch((error) => {
                console.error(error);
            });

	}
	else {
		mappy.clearSource('nearbyPlaces');
        $('#update_nearby').hide();
	}
}
