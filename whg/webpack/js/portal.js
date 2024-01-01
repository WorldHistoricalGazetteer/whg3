// /whg/webpack/portal.js

import datasetLayers from './mapLayerStyles';
import nearPlaceLayers from './nearPlaceLayerStyles';
import throttle from 'lodash/throttle';
import { attributionString, deepCopy, geomsGeoJSON } from './utilities';
import Dateline from './dateline';
import { popupFeatureHTML } from './getPlace.js';

import '../css/mapAndTableMirrored.css';
import '../css/dateline.css';
import '../css/portal.css';

const payload = JSON.parse($('#payload_data').text());

let mapParameters = {
	style: [ 'OUTDOOR.DEFAULT', 'TOPO.DEFAULT', 'TOPO.TOPOGRAPHIQUE', 'SATELLITE.DEFAULT', 'OCEAN.DEFAULT' ], 
	maxZoom: 17,
	navigationControl: true,
	controls: {temporal: temporal},
}
let mappy = new whg_maplibre.Map(mapParameters);

let baseStyle = {};

let nullCollection = {
    type: 'FeatureCollection',
    features: []
}
const noSources = $('<div>').html('<i>None - please adjust time slider.</i>').hide();

let featureCollection;
let relatedFeatureCollection;
let nearbyFeatureCollection;
let featureHighlights = [];
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

			const controlContainer = document.querySelector('.maplibregl-control-container');
			controlContainer.setAttribute('id', 'mapControls');
			controlContainer.classList.add('item');

			const mapOverlays = document.createElement('div');
			mapOverlays.id = 'mapOverlays';
			mappy.getContainer().appendChild(mapOverlays);

			['left', 'centre', 'right'].forEach(function(side) {
				const column = document.createElement('div');
				column.classList.add('column', side);
				mapOverlays.appendChild(column);
				const overlays = document.querySelectorAll('.overlay.' + side);
				overlays.forEach(function(overlay) {
					if (overlay.id == 'map') {
						column.appendChild(controlContainer);
						overlay.classList.remove('overlay','left','right');
					}
					else {
						column.appendChild(overlay);
						overlay.classList.add('item');
					}
				})
			});

			const currentStyle = mappy.getStyle();
			baseStyle.sources = Object.keys(currentStyle.sources);
	    	baseStyle.layers = currentStyle.layers.map((layer) => layer.id);

            mappy.addSource('nearbyPlaces', {
				'type': 'geojson',
			    'data': nullCollection,
			});
		    nearPlaceLayers.forEach(layer => {
				mappy.addLayer(layer);
			});

            mappy.addSource('places', {
				'type': 'geojson',
			    'data': nullCollection,
				'attribution': attributionString(),
			});
		    datasetLayers.forEach(layer => {
				mappy.addLayer(layer);
				mappy.setFilter(layer.id, [
					'all',
					layer.filter,
					['!=', 'outOfDateRange', true],
				]);
			});

	  		const geoLayers = JSON.parse($('#geo-layers').text());
			if (geoLayers.length > 0) {
				$('#map_options').append(createGeoLayerSelectors('geoLayers', geoLayers));
			}

			if (mapParameters.style.length !== 1) {
				$('#map_options').append(createBasemapRadioButtons());
			}

			$('#map_options').append(createNearbyPlacesControl());
			
			const dateRangeChanged = throttle(() => { // Uses imported lodash function
			    filterSources();
			}, 300);

			if (!!mapParameters.controls.temporal) {
				let datelineContainer = document.createElement('div');
				datelineContainer.id = 'dateline';
				document.getElementById('mapControls').appendChild(datelineContainer);
				window.dateline = new Dateline({
					...mapParameters.controls.temporal,
					onChange: dateRangeChanged
				});
			};
			$(window.dateline.button).on('click', dateRangeChanged);

			mappy.on('mousemove', function(e) {
				const features = mappy.queryRenderedFeatures(e.point);

				function clearHighlights() {
					if (featureHighlights.length > 0) {
						mappy.getCanvas().style.cursor = 'grab';
						featureHighlights.forEach(featureHighlight => {
							mappy.setFeatureState(featureHighlight, { highlight: false });
							$('.source-box').eq(featureHighlight.id).removeClass('highlight');
						});
						featureHighlights = [];
					}
				}

				if (!showingRelated) {
					if (features.length > 0) {
						clearHighlights();
						features.forEach(feature => { // Check datasetLayers, starting with topmost layers
							if (!datasetLayers.some(layer => feature.layer.id == layer.id)) {
								return; // Reached underlying layers - exit loop
							}
							let featureHighlight = { source: feature.source, id: feature.id, geom: featureCollection.features[feature.id].geometry };
							mappy.setFeatureState(featureHighlight, { highlight: true });
							$('.source-box').eq(featureHighlight.id).addClass('highlight');
							featureHighlights.push(featureHighlight);

						});
						features.forEach(feature => { // Check nearPlaceLayers, starting with topmost layers
							if (!nearPlaceLayers.some(layer => feature.layer.id == layer.id)) {
								return; // Reached underlying layers - exit loop
							}
							nearPlacePopup
							.setLngLat(e.lngLat)
							.setHTML(popupFeatureHTML(feature, false)); // second parameter indicates clickability
						$(nearPlacePopup.getElement()).show();
						});
						if (featureHighlights.length > 0) {
							mappy.getCanvas().style.cursor = 'pointer';
						}

					} else {
						clearHighlights();
						$(nearPlacePopup.getElement()).hide();
					}
				}

			});

			mappy.on('click', function() {
				if (!showingRelated && featureHighlights.length > 0) {
					mappy.fitViewport( bbox( geomsGeoJSON(featureHighlights) ) );
				}
			});

			mappy.getContainer().style.opacity = 1;

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

    	const collectionList = $('#collection_list');
    	const ul = $('<ul>').addClass('coll-list');
    	payload.forEach(dataset => {
		  	if (dataset.collections.length > 0) {
				  dataset.collections.forEach(collection => {
			            let listItem = '';
			            if (collection.class === 'place') {
			                listItem = `
			                    <a href="${ collection.url }" target="_blank">
			                        <b>${ collection.title.trim() }</b>
			                    </a>, a collection of <sr>${ collection.count }</sr> places.
			                    <span class="showing"><p>${ collection.description }</p></span>
			                    [<a href="javascript:void(0);" data-id="${ collection.id }" class="show-collection"><span>show</span><span class="showing">hide</span></a>]
			                `;
			            } else {
			                listItem = `
			                    <a href="${ collection.url }" target="_blank">
			                        <b>${title}</b>
			                    </a>, a collection of all <sr>${ collection.count }</sr> places in datasets
			                `;
			            }
			            ul.append($('<li>').html(listItem));
				  });
			}
		});
		if (ul.find('li').length > 0) {
		    collectionList.append(ul);
		}
		else {
			collectionList.html('<i>None yet</i>');
		}
		
		$('#sources').append(noSources);

		featureCollection = geomsGeoJSON(payload);
		console.log(featureCollection);
		mappy.getSource('places').setData(featureCollection);
		// Do not use fitBounds or flyTo due to padding bug in MapLibre/Maptiler
		mappy.fitViewport( bbox(featureCollection) );

	  	var min = Math.min.apply(null, allts.map(function(row) {
	  		return Math.min.apply(Math, row);
	  	}));
	  	var max = Math.max.apply(null, allts.map(function(row) {
	  		return Math.max.apply(Math, row);
	  	}));
	  	let minmax = [min, max]
	  	// feed to #histogram
	  	histogram_data(allts, minmax)

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
				  mappy.fitViewport( bbox( featureCollection ) );
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
						mappy.fitViewport( bbox(relatedFeatureCollection) );
			  		});
			  	showingRelated = true;
			}
			else {
				mappy.getSource('places').setData(featureCollection);
				mappy.fitViewport( bbox(featureCollection) );
				showingRelated = false;
			}
	  	})

        document.querySelectorAll('.toggle-link').forEach(link => {
            link.addEventListener('click', function(event) {
                toggleVariants(event, this);
            });
        });
    })
    .catch(error => console.error("An error occurred:", error));
    
function filterSources() {
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
}

function range(start, stop, step) {
	var a = [start],
		b = start;
	while (b < stop) {
		a.push(b += step || 1);
	}
	return a;
}

function intersects(a, b) {
	let min = (a[0] < b[0] ? a : b)
	let max = (min == a ? b : a)
	return !(min[1] < max[1])
}

function histogram_data(intervals, minmax) {
	let step = Number(((minmax[1] - minmax[0]) / 200))
	let bins = range(minmax[0], minmax[1], step)
	let hist_array = Array.apply(null, Array(bins.length)).map(Number.prototype.valueOf, 0);
	let labels = bins.map(function(d) {
		return Math.round(d)
	})
	for (var b = 0; b < bins.length; b++) {
		let bin = Array(bins[b], bins[b + 1])
		for (var i in intervals) {
			if (intersects(bin, intervals[i])) {
				hist_array[b] += 1
			}
		}
	}
	let data = hist_array.map(function(d, i) {
		return {
			"bin": labels[i],
			"count": d
		}
	})

	// visualize it
	histogram(data, labels, minmax)

}

function histogram(data, labels, minmax) {
	// exit if no data
	if (data[0].bin == "Infinity") {
		$("#histogram").html('<i>None yet</i>');
		return;
	}
	data = data.slice(0, 200)
	let curwidth = $("#histogram").width()

	var margin = {
			top: 0,
			right: 10,
			bottom: 0,
			left: 10
		},
		width = 400,
		height = 30,
		padding_h = 20,
		padding_w = 30;

	// set the ranges
	window.xScale = d3.scaleLinear()
		.range([0, width])
	window.yScale = d3.scaleLinear()
		.range([height, 0]);

	xScale.domain(minmax);
	yScale.domain([0, d3.max(data, function(d) {
		return d.count;
	})]);

	// TODO: responsive scaling of svg width
	window.svg_hist = d3.select("#histogram").append("svg")
		.attr("width", '100%')
		.attr("height", height + padding_h)

		.attr('viewBox', '0 0 ' + Math.min(width, height + padding_h) + ' ' + Math.min(width, height + padding_h))
		.attr('preserveAspectRatio', 'xMinYMin')

		.append("g")
		.attr("transform", "translate(" + margin.left + "," + margin.top + ")")

	window.axisB = d3.axisBottom(xScale)
		.tickValues(labels.filter(function(d, i) {
			return !(i % 20)
		}))
		.tickFormat(d3.format("d"));

	var axisL = d3.axisLeft(yScale)

	svg_hist.selectAll(".bar")
		.data(data)
		.enter().append("rect")
		.attr("class", "bar")
		.attr("x", function(d) {
			return xScale(d.bin);
		})
		//.attr("width", function(d) { return xScale(d.x1) - xScale(d.x0) -1 ; })
		.attr("width", 2)
		.attr("y", function(d) {
			return yScale(d.count);
		})
		.attr("height", function(d) {
			return height - yScale(d.count);
		});

	var xAxis = svg_hist.append("g")
		.attr("id", "xaxis")
		.attr("transform", "translate(0," + height + ")")
		.call(axisB)
}

function onBasemapRadioChange() {
	const variantValue = $(this).val();
	const style_code = variantValue.split(".");
	console.log('Selected variant: ', variantValue, whg_maplibre.MapStyle[style_code[0]][style_code[1]]);
	mappy.setStyle(whg_maplibre.MapStyle[style_code[0]][style_code[1]]/*, {
		transformStyle: (previousStyle, nextStyle) => {
			const newSources = {
				...nextStyle.sources
			};
			console.log(previousStyle.sources,newSources);
			Object.keys(previousStyle.sources).forEach((sourceId) => {
				if (!baseStyle.sources.includes(sourceId)) {
					newSources[sourceId] = previousStyle.sources[sourceId];
				}
			});
			const additionalLayers = previousStyle.layers.filter((layer) => !baseStyle.layers.includes(layer.id));
			baseStyle.sources = Object.keys(nextStyle.sources);
			baseStyle.layers = nextStyle.layers.map((layer) => layer.id);
			return {
				...nextStyle,
				sources: newSources,
				layers: [...nextStyle.layers, ...additionalLayers],
			};
		}
	}*/);
}

function createBasemapRadioButtons() {
    const styleFilterValues = mapParameters.style.map(value => value.split('.')[0]);
    const $radioContainer = $('<div>').addClass('option-block');
    $('<p>').addClass('strong-red heading').text('Basemap Style').appendTo($radioContainer);

    const $itemDiv = $('<div>').addClass('geoLayer-choice');
	const $checkboxItem = $('<input>')
        .attr('id', '3D_selector')
        .attr('type', 'checkbox')
        .attr('disabled', 'disabled') // TODO
        /*.on('change', switch3D)*/; // TODO
    const $label = $(`<label for = '3D_selector'>`).text('Enable 3D');
    $itemDiv.append($checkboxItem, $label);
    $radioContainer.append($itemDiv);

    console.log(mappy.getStyle());

    for (const group of Object.values(whg_maplibre.MapStyle)) {
        if (mapParameters.style.length == 0 || styleFilterValues.includes(group.id)) {
            const $groupItem = $('<div>').addClass('group-item').text(group.name);

            for (const orderedVariant of group.orderedVariants) {
                const datasetValue = group.id + '.' + orderedVariant.variantType;
                if (mapParameters.style.length == 0 || mapParameters.style.includes(datasetValue)) {
            		const $itemDiv = $('<div>').addClass('basemap-choice');
					const itemID = datasetValue.replace('.','-').toLowerCase();
                    const $radioItem = $('<input>')
                        .attr('id', itemID)
                        .attr('type', 'radio')
                        .attr('name', 'basemap-style')
                        .attr('value', datasetValue)
                        .attr('checked', datasetValue == mapParameters.style[0])
                        .on('change', onBasemapRadioChange);
                    const $label = $(`<label for = '${ itemID }'>`).text(orderedVariant.name);
                    $itemDiv.append($radioItem, $label);
                    $groupItem.append($itemDiv);
                }
            }

            $radioContainer.append($groupItem);
        }
    }

    return $radioContainer;
}

function onGeoLayerSelectorChange() {
    const geoLayerValue = $(this).val();
    console.log('Selected GeoLayer: ', geoLayerValue);
}

function createGeoLayerSelectors(heading, geoLayers) {
    const $geoLayersContainer = $('<div>').addClass('option-block');
    $('<p>').addClass('strong-red heading').text(heading).appendTo($geoLayersContainer);
    geoLayers.forEach((geoLayer, i) => {
		const itemID = `geoLayer_${i}`;
		const $itemDiv = $('<div>').addClass('geoLayer-choice');
		const $checkboxItem = $('<input>')
            .attr('id', itemID)
            .attr('type', 'checkbox')
            .attr('value', geoLayer)
        	.attr('disabled', 'disabled') // TODO
            .on('change', onGeoLayerSelectorChange);
        const $label = $(`<label for = '${ itemID }'>`).text(geoLayer);
        $itemDiv.append($checkboxItem, $label);
        $geoLayersContainer.append($itemDiv);
	});

    return $geoLayersContainer;
}

function nearbyPlaces() {
	if ( $('#nearby_places').prop('checked') ) {
        const center = mappy.getCenter();
        const radius = $('#radiusSelect').val();
        const lon = center.lng;
        const lat = center.lat;
        $('button#update_nearby').show();

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
				$('button#update_nearby').html(`<span class="strong-red">${nearbyFeatureCollection.features.length}</span> Update`);
				if (!showingRelated && nearbyFeatureCollection.features.length > 0) {
					mappy.fitViewport( bbox( nearbyFeatureCollection ) );
				}
            })
            .catch((error) => {
                console.error(error);
            });

	}
	else {
		mappy.getSource('nearbyPlaces').setData(nullCollection);
        $('button#update_nearby').hide();
	}
}

function createNearbyPlacesControl() {
    const $nearbyPlacesControl = $('<div>').addClass('option-block');
    $('<p>').addClass('strong-red heading').text('Nearby Places').appendTo($nearbyPlacesControl);
    const $itemDiv = $('<div>').addClass('geoLayer-choice');
	const $checkboxItem = $('<input>')
        .attr('id', 'nearby_places')
        .attr('type', 'checkbox')
        //.attr('disabled', 'disabled')
        .on('change', nearbyPlaces);
    const $label = $(`<label for = 'nearby_places'>`).text('Show');
    $itemDiv.append($checkboxItem, $label);
    
    const $button = $('<button>')
    	.attr('id', 'update_nearby')
    	.attr('title', 'Search again - based on map center')
    	.html('Update')
    	.on('click', nearbyPlaces)
    	.hide();

    const $radiusLabel = $(`<label for = 'radiusSelect'>`).text('Radius: ');
    const $select = $('<select>')
    	.attr('title', 'Search radius, based on map center')
    	.attr('id', 'radiusSelect');
    for (let i = 1; i <= 10; i++) {
        const $option = $('<option>')
            .attr('value', i**2)
            .text(`${i**2} km`);
        $select.append($option);
    }
    $select.val(16).on('change', nearbyPlaces);

    $nearbyPlacesControl.append($button, $itemDiv, $radiusLabel, $select);

    return $nearbyPlacesControl;
}
