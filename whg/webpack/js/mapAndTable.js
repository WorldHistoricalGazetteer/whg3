// /whg/webpack/js/mapAndTable.js

import Dateline from './dateline';
import generateMapImage from './saveMapImage';
import ClipboardJS from '/webpack/node_modules/clipboard'; 

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
let dateline = null;
let datelineContainer = null;

if (!!mapParameters.controls.navigation) map.addControl(new maptilersdk.NavigationControl(), 'top-left');

class fullScreenControl {
	onAdd() { 
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
		this._container.textContent = 'Basemap';
		this._container.innerHTML =
			'<button type="button" class="maplibregl-ctrl-fullscreen" aria-label="Enter fullscreen" title="Enter fullscreen">' +
			'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
			'</button>';
		return this._container;
	}
}

class downloadMapControl {
	onAdd() {
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
		this._container.textContent = 'Basemap';
		this._container.innerHTML =
			'<button type="button" class="download-map-button" aria-label="Download map image" title="Download map image">' +
			'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
			'</button>';
		return this._container;
	}
}

class StyleControl {
	onAdd() {
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
		this._container.textContent = 'Basemap';
		this._container.innerHTML =
			'<button type="button" class="style-button" aria-label="Change basemap style" title="Change basemap style">' +
			'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
			'</button>';
		this._container.querySelector('.style-button').addEventListener('click', this._onClick.bind(this));
		return this._container;
	}

	onRemove() {
		this._container.parentNode.removeChild(this._container);
		this._map = undefined;
	}

	_onClick() {
		let styleList = document.getElementById('mapStyleList');
		if (!styleList) {
			styleList = document.createElement('ul');
			styleList.id = 'mapStyleList';
			styleList.className = 'maplibre-styles-list';
			const styleFilterValues = mapParameters.styleFilter.map(value => value.split('.')[0]);
			for (const group of Object.values(maptilersdk.MapStyle)) {
				// Check if the group.id is in the styleFilter array
				if (mapParameters.styleFilter.length == 0 || styleFilterValues.includes(group.id)) {
					const groupItem = document.createElement('li');
					groupItem.textContent = group.name;
					groupItem.className = 'group-item';
					const variantList = document.createElement('ul');
					variantList.className = 'variant-list';
					for (const orderedVariant of group.orderedVariants) {
						const datasetValue = group.id + '.' + orderedVariant.variantType;
						if (mapParameters.styleFilter.length == 0 || mapParameters.styleFilter.includes(datasetValue)) {
							const variantItem = document.createElement('li');
							variantItem.textContent = orderedVariant.name;
							variantItem.className = 'variant-item';
							variantItem.dataset.value = datasetValue;
							variantItem.addEventListener('click', this._onVariantClick.bind(this));
							variantList.appendChild(variantItem);
						}
					}
					groupItem.appendChild(variantList);
					styleList.appendChild(groupItem);
				}
			}
			this._container.appendChild(styleList);
		}

		styleList.classList.toggle('show');
	}

	_onVariantClick(event) {
		const variantValue = event.target.dataset.value;
		console.log('Selected variant: ', variantValue);
		const style_code = variantValue.split(".");
		mappy.setStyle(maptilersdk.MapStyle[style_code[0]][style_code[1]]);
		renderData(pageData);
		const styleList = document.getElementById('mapStyleList');
		if (styleList) {
			styleList.classList.remove('show');
		}
	}
}

mappy.addControl(new fullScreenControl(), 'top-left');
mappy.addControl(new downloadMapControl(), 'top-left');

let style_code;
if (mapParameters.styleFilter.length !== 1) {
	mappy.addControl(new StyleControl(), 'top-right');
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

	// Control positioning of map, clear of overlays
	function setMapPadding() {
		const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
		const OverlaysRect = document.getElementById('mapOverlays').getBoundingClientRect();
		mapPadding = {
			top: ControlsRect.top - OverlaysRect.top,
			bottom: OverlaysRect.bottom - ControlsRect.bottom,
			left: ControlsRect.left - OverlaysRect.left,
			right: OverlaysRect.right - ControlsRect.right,
		};
		if (mapBounds) {
			if (Array.isArray(mapBounds) || !mapBounds.hasOwnProperty('center')) { // mapBounds might be a coordinate pair object returned by mappy.getBounds();
				mappy.fitBounds(mapBounds, {
					padding: mapPadding,
					duration: 0
				});
			} else { // mapBounds has been set based on a center point and zoom
				mappy.flyTo({
					...mapBounds,
					padding: mapPadding,
					duration: 0
				})
			}
		}
		// console.log('mapPadding calculated:', mapBounds, mapPadding);
	}
	const resizeObserver = new ResizeObserver(entries => {
		setMapPadding();
	});

	setMapPadding();
	// Recalculate mapPadding whenever its viewport changes size
	resizeObserver.observe(document.getElementById('mapControls'));
	resizeObserver.observe(document.getElementById('mapOverlays'));

	mapBounds = mappy.getBounds();
	mappy.fitBounds(mapBounds, {
		padding: mapPadding,
		duration: 0
	});
	whgMap.style.opacity = 1;
	/*
		// Not sufficiently precise
		function getPaddedBounds() {
			const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
			const MapRect = document.getElementById(mapParameters.container).getBoundingClientRect();
			const lowerLeftPixel = [MapRect.left - ControlsRect.left, MapRect.height - (MapRect.bottom - ControlsRect.bottom)];
			const topRightPixel = [ControlsRect.width + (MapRect.left - ControlsRect.left), MapRect.height - ControlsRect.height];
			// Convert pixel coordinates to map coordinates
		    const lowerLeftLngLat = mappy.unproject(lowerLeftPixel).toArray();
		    const topRightLngLat = mappy.unproject(topRightPixel).toArray();
		    return [...lowerLeftLngLat, ...topRightLngLat];
		}
		mappy.on('moveend', function() {
		    console.log('Old mapBounds:', mapBounds);
		    mapBounds = getPaddedBounds();
		    console.log('New mapBounds:', mapBounds);
		});
	*/
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

	renderData(pageData);

	const layer_list = ['outline', 'gl_active_point', 'gl_active_line', 'gl_active_poly']

	let activePopup;
	for (var l in layer_list) {
	    mappy.on('mouseenter', layer_list[l], function(e) {
	        mappy.getCanvas().style.cursor = 'pointer';
	        
	        var pid = e.features[0].properties.pid;
	        var title = e.features[0].properties.title;
	        var min = e.features[0].properties.min;
	        var max = e.features[0].properties.max;
	
	        if (activePopup) {
	            activePopup.remove();
	        }
	        activePopup = new maptilersdk.Popup({ closeButton: false })
	            .setLngLat(e.lngLat)
	            .setHTML('<b>' + title + '</b><br/>' +
	                'Temporality: ' + (min ? min : '?') + '/' + (max ? max : '?') + '<br/>' +
	                'Click to focus'
	            )
	            .addTo(mappy);
	        activePopup.pid = pid;
	    });

		mappy.on('mousemove', function(e) {
		    if (activePopup) {
		        activePopup.setLngLat(e.lngLat);
		    }
		});

		mappy.on('mouseleave', layer_list[l], function() {
			mappy.getCanvas().style.cursor = '';
		    if (activePopup) {
		      activePopup.remove();
		    }
		    
		});

		mappy.on('click', layer_list[l], function(e) {
			
			var pid;
			if (activePopup && activePopup.pid) {
        		pid = activePopup.pid;
		      	activePopup.remove();
        	} else pid = e.features[0].properties.pid;
			var table = $('#placetable').DataTable();
		    
		    // Search for the row within the sorted and filtered view
		    var pageInfo = table.page.info();
		    var rowPosition = -1;
			var rows = table.rows({ search: 'applied', order: 'current' }).nodes();
			let selectedRow;
			for (var i = 0; i < rows.length; i++) {
			    var rowData = table.row(rows[i]).data();
			    rowPosition++;
			    if (rowData.properties.pid == pid) {
			        selectedRow = rows[i];
			        break; // Stop the loop when the row is found
			    }
			}

		    if (rowPosition !== -1) {
		        // Calculate the page number based on the row's position
		        var pageNumber = Math.floor(rowPosition / pageInfo.length);
		        console.log(`Feature ${pid} selected at table row ${rowPosition} on page ${pageNumber + 1} (current page ${pageInfo.page + 1}).`);
		        
		        // Check if the row is on the current page
		        if (pageInfo.page !== pageNumber) {
		            table.page(pageNumber).draw('page');
		        }
		
		        selectedRow.scrollIntoView();
		        $(selectedRow).trigger('click');
		    }
			
		})
	}

	document.addEventListener('click', function(event) {

		if (event.target && event.target.classList.contains('fetch-info-link')) {
			const pid = event.target.getAttribute('data-pid');
			getPlace(pid);
			event.preventDefault();
		}

		if (event.target && event.target.parentNode && event.target.parentNode.classList.contains('download-map-button')) {
			generateMapImage(mappy);
		}

		if (event.target && event.target.parentNode) {
			const parentNodeClassList = event.target.parentNode.classList;

			if (parentNodeClassList.contains('maplibregl-ctrl-fullscreen')) {
				console.log('Switching to fullscreen.');
				parentNodeClassList.replace('maplibregl-ctrl-fullscreen', 'maplibregl-ctrl-shrink');
				document.getElementById('mapOverlays').classList.add('fullscreen');

			} else if (parentNodeClassList.contains('maplibregl-ctrl-shrink')) {
				console.log('Switching off fullscreen.');
				parentNodeClassList.replace('maplibregl-ctrl-shrink', 'maplibregl-ctrl-fullscreen');
				document.getElementById('mapOverlays').classList.remove('fullscreen');
			}
		}

	});

});

const datasetLayers = [{
		'id': 'gl_active_line',
		'type': 'line',
		'source': 'places',
		'paint': {
			'line-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.8)', // green
				'rgba(144,238,144,.8)' // lightgreen
			],
			'line-width': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 2,
				1
			]
		},
		'filter': ['==', '$type', 'LineString']
	},
	{
		'id': 'gl_active_poly',
		'type': 'fill',
		'source': 'places',
		'paint': {
			'fill-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0,.8)', // green
				'rgba(221,221,221,.3)' // pale-gray
			],
			'fill-outline-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'red',
				['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], 'rgba(102,102,102,.5)', // dark-gray
				'rgba(102,102,102,.8)' // dark-gray
			],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'outline',
		'type': 'line',
		'source': 'places',
		'layout': {},
		'paint': {
			'line-color': 'rgba(153,153,153,.5)', // mid-gray
			'line-width': 1,
			'line-dasharray': [4, 2],
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_point',
		'type': 'circle',
		'source': 'places',
		'paint': {
			'circle-stroke-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgb(255,0,0)',	// red			
				'rgb(255,165,0)' // orange
	        ],
			'circle-stroke-opacity': [
	            'case',
				['any', ['==', ['get', 'min'], 'null'], ['==', ['get', 'max'], 'null']], .5,			
				.8
	        ],
			'circle-stroke-width': [ // Simulate larger radius - zoom-based radius cannot operate together with feature-state switching
				'case',
				['boolean', ['feature-state', 'highlight'], false], 5,
				2
			],
			'circle-radius': [
				'interpolate',
				['linear'],
				['zoom'],
				0, .5, // zoom, radius
				16, 20,
			],
	        'circle-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'rgba(255,0,0,.8)',	// red
				'rgba(255,165,0,.5)' // orange
	        ],
		},
		'filter': ['==', '$type', 'Point'],
	}
]

function filteredLayer(layer) {
	if ($('.range_container.expanded').length > 0) { // Is dateline active?
		const modifiedLayer = ({
			...layer
		});
		const existingFilter = modifiedLayer.filter;
		
		const isUndatedChecked = $('#undated_checkbox').is(':checked');
		
		if (isUndatedChecked) { // Include features within the range AND undated features
		  modifiedLayer.filter = [
		    'all',
		    existingFilter,
		    [
				'any',
				[
				    'all',
				    ['!=', 'max', 'null'],
				    ['!=', 'min', 'null'],
				    ['>=', 'max', dateline.fromValue],
				    ['<=', 'min', dateline.toValue],
				],
				[
					'any',
                    ['==', 'max', 'null'],
                    ['==', 'min', 'null']
				]
			]
		  ];
		} else { // Include features within the range BUT NOT undated features
		  modifiedLayer.filter = [
		    'all',
		    existingFilter,
		    ['has', 'max'],
		    ['has', 'min'],
		    ['>=', 'max', dateline.fromValue],
		    ['<=', 'min', dateline.toValue],
		  ];
		}
		
		return modifiedLayer;
	} else return layer;
}

// fetch and render
function renderData(dsid) {
	/*startSpinner("spinner_map", "map_browse");*/

	// clear any data layers and 'places' source
	datasetLayers.forEach(function(layer, z) {
		if (!!mappy.getLayer(layer.id)) mappy.removeLayer(layer.id);
		if (!!mappy.getLayer('z-index-' + z)) mappy.removeLayer('z-index-' + z);
	});
	if (!!mappy.getSource('places')) mappy.removeSource('places')

	// fetch data
	$.get('/datasets/' + dsid + '/mapdata', function(data) {
		features = data.features;
		
		// Log features with invalid geometry
	    const invalidFeatures = features.filter(feature => {
	        return !feature.geometry;
	    });
	    console.log('Invalid Features:', invalidFeatures);
		
		
		initialiseTable();
		//console.log('data', data);
		
		let attributionParts = [];
		if (data.attribution) {
		    attributionParts.push(data.attribution);
		}
		if (data.citation) {
		    attributionParts.push(data.citation);
		}
		let attribution = '';
		if (attributionParts.length > 0) attribution = attributionParts.join(', ');
		
		let attributionStringParts = ['&copy; World Historical Gazetteer & contributors'];
		attributionStringParts.push(data.attribution || data.citation || attribution);

		// add source 'places' w/retrieved data
		mappy.addSource('places', {
			'type': 'geojson',
			'data': data,
			'attribution': attributionStringParts.join(' | '),
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
			mappy.addLayer(filteredLayer(layer));
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

		console.log('Data layers added, map fitted.', mapBounds, mapPadding);
		/*spinner_map.stop()*/


	}) // get
}

let checked_rows;
let highlightedFeatureIndex;
let table;

$("[rel='tooltip']").tooltip();

var clip_cite = new ClipboardJS('#a_clipcite');
clip_cite.on('success', function(e) {
	console.log('clipped')
	e.clearSelection();
	$("#a_clipcite").tooltip('hide')
		.attr('data-original-title', 'copied!')
		.tooltip('show');
});

$("#clearlines").click(function() {
	mappy.removeLayer('gl_active_poly')
	mappy.removeLayer('outline')
})

$("#create_coll_link").click(function() {
	console.log('open title input')
	$("#title_form").show()
})

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
		mappy.setFilter(layer.id, on ? filteredLayer(layer).filter : layer.filter);
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

function resetSearch() {
	var e = $.Event('keyup')
	e.which(13)
	$("#placetable_filter input").trigger(e)
}

// pids generate new CollPlace (collection_collplace) and
// TraceAnnotation records (trace_annotations
// same function in place_portal.html
function add_to_collection(coll, pids) {
	console.log('add_to_collection()')
	var formData = new FormData()
	formData.append('collection', coll)
	formData.append('place_list', pids)
	formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');
	/* collection.views.add_places() */
	$.ajax({
		type: 'POST',
		enctype: 'multipart/form-data',
		url: '/collections/add_places/',
		processData: false,
		contentType: false,
		cache: false,
		data: formData,
		success: function(response) {
			var dupes = response.msg.dupes
			var added = response.msg.added
			if (dupes.length > 0) {
				let msg = dupes.length + ' records ' + (dupes.length > 1 ? 'were' : "was") + ' already in the collection: [' + dupes
				if (added.length > 0) {
					msg += ']; ' + added.length + ' ' + (added.length > 1 ? 'were' : "was") + ' added'
				}
				alert(msg)
			} else {
				// notify success & clear checks and list
				$("#added_flash").fadeIn().delay(2000).fadeOut()
				checked_rows = []
			}
			// uncheck everything regardless
			$(".table-chk").prop('checked', false)
		}
	})
	// TODO: notify of success
	console.log('add_to_collection() completed')
	/*$("#addtocoll").hide()*/
	$("#addtocoll_popup").hide()
	$("#sel_count").html('')
	$("#selection_status").css('display', 'none')
	/*$("input.action").prop('checked',false)*/
	/*resetSearch()*/
}
$(".a_addtocoll").click(function() {
	coll = $(this).attr('ref')
	pids = checked_rows
	add_to_collection(coll, pids)
	/*console.log('pids to coll', pids, coll)*/
})
$("#b_create_coll").click(function() {
	let title = $("#title_input").val()
	if (title != '') {
		// create new place collection, return id
		var formData = new FormData()
		formData.append('title', title)
		formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');
		$.ajax({
			type: 'POST',
			enctype: 'multipart/form-data',
			url: '/collections/flash_create/',
			processData: false,
			contentType: false,
			cache: false,
			data: formData,
			success: function(data) {
				el = $('<li><a class="a_addtocoll" href="#" ref=' + data.id + '>' + data.title + '</a></li>')
				el.click(function() {
					coll = data.id
					pids = checked_rows
					add_to_collection(coll, pids)
					console.log('pids to coll', pids, coll)
				})
				$("#my_collections").append(el)
			}
		})
		$("#title_form").hide()
	} else {
		alert('Your new collection needs a title!')
	}
})

function filterColumn(i, v) {
	// clear then search
	table
		.columns([1])
		.search('')
		.columns(i)
		.search(v)
		.draw();
	$("#status_select").val(localStorage.getItem('filter'))
}

function clearFilters() {
	// clear
	table
		.columns([1])
		.search('')
		.draw();
	$("#status_select").val('99')
}

function highlightFeature(pid) {
	
	var featureIndex = features.findIndex(f => f.properties.pid === parseInt(pid)); // .addSource 'generateId': true doesn't create a findable .id property
	if (featureIndex !== -1) {
		if (highlightedFeatureIndex !== undefined) mappy.setFeatureState({ source: 'places', id: highlightedFeatureIndex }, { highlight: false });
	    var feature = features[featureIndex];
		const geom = feature.geometry;
		if (geom) {
			const coords = geom.coordinates;
			highlightedFeatureIndex = featureIndex;
			mappy.setFeatureState({ source: 'places', id: featureIndex }, { highlight: true });
			
			// zoom to feature
			if (geom.type.toLowerCase() == 'point') {
				const flycoords = typeof(coords[0]) == 'number' ? coords : coords[0]
				const mapBounds = {
					'center': flycoords,
					'zoom': 7
				}
				mappy.flyTo({
					...mapBounds,
					padding: mapPadding
				})
			} else {
				mapBounds = envelope(geom).bbox
				mappy.fitBounds(mapBounds, {
					padding: mapPadding
				})
			}
		}
		else {
			console.log('Feature in clicked row has no geometry.');
		}
	} else {
	    console.log(`Feature ${pid} not found.`);
	}
	
}

// TODO: use datatables methods?
// Listen for table row click (assigned using event delegation to allow for redrawing)
$("body").on("click", "#placetable tbody tr", function() {
	const thisy = $(this)
	// get id
	const pid = $(this)[0].cells[0].textContent
	// is checkbox checked?
	// if not, ensure row pid is not in checked_rows
	if (loggedin == true) {
		chkbox = thisy[0].cells[3].firstChild
		if (chkbox.checked) {
			console.log('chkbox.checked')
			checked_rows.push(pid)
			$("#selection_status").fadeIn()
			/*$("#addtocoll").fadeIn()*/
			console.log('checked_rows', checked_rows)
			$("#sel_count").html(' ' + checked_rows.length + ' ')
		} else {
			const index = checked_rows.indexOf(pid);
			if (index > -1) {
				checked_rows.splice(index, 1)
				if (checked_rows.length == 0) {
					$("#addtocoll").fadeOut()
					$("#addtocoll_popup").hide()
				}
			}
			console.log(pid + ' removed from checked_rows[]', checked_rows)
		}
	}
	
	// highlight this row, clear others
	var selected = $(this).hasClass("highlight-row");
	$("#placetable tr").removeClass("highlight-row");

	if (!selected)
		$(this).removeClass("rowhover");
	$(this).addClass("highlight-row");
	
	// fetch its detail
	getPlace(pid);
	
	highlightFeature(pid);

});

function highlightFirstRow() {
	$("#placetable tr").removeClass("highlight-row");
	const row = $("#ds_table table tbody")[0].rows[0]
	const pid = parseInt(row.cells[0].textContent)
	// highlight first row, fetch detail, but don't zoomTo() it
	$("#placetable tbody").find('tr').eq(0).addClass('highlight-row')
	getPlace(pid)
}

// Adjust the DataTable's page length to avoid scrolling where possible
function adjustPageLength() {
    const dsTable = document.getElementById('ds_table');
    const tableFilter = document.getElementById('placetable_filter');
    const tablePaginate = document.getElementById('placetable_paginate');
    const theadRow = document.querySelector('#placetable thead tr');
    const tbody = document.querySelector('#placetable tbody');
    const availableHeight = dsTable.clientHeight - (2 * 10 /*padding*/) - tableFilter.clientHeight - tablePaginate.clientHeight - theadRow.clientHeight;
    const averageRowHeight = 2 + ( tbody.clientHeight / document.querySelectorAll('#placetable tr:not(thead tr)').length );
    let estimatedRowsPerPage = Math.floor(availableHeight / ( averageRowHeight ));
  	// Ensure a minimum of 5 rows
  	estimatedRowsPerPage = Math.max(estimatedRowsPerPage, 5);
	console.log(`Changing table length to ${estimatedRowsPerPage} rows @${averageRowHeight} pixels.`);
  	const DataTable = $('#placetable').DataTable();
  	DataTable.page.len(estimatedRowsPerPage).draw();
}

$(".table-chk").click(function(e) {
	e.preventDefault()
	console.log('adding', $(this).data('id'))
	/*console.log('checked_rows',checked_rows)*/
})

function initialiseTable() {
	
	console.log('initialiseTable', features);
	
	// START ds_info controls
	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';

	// Set initial height and icon
	if (isCollapsed) {
		$('#ds_info').css('height', '40px');
		$('#expandIcon').show();
		$('#collapseIcon').hide();
		$('#iconLabel').text('Show Detail');
	}

	$('#toggleIcon').click(function() {
		if (isCollapsed) {
			// if the div is collapsed, expand it to fit its content
			$('#ds_info').css('height', 'fit-content');
			$('#expandIcon').hide();
			$('#collapseIcon').show();
			$('#iconLabel').text('Hide');
			isCollapsed = false;
		} else {
			// if the div is not collapsed, animate it to 40px height
			$('#ds_info').css('height', '40px');
			$('#expandIcon').show();
			$('#collapseIcon').hide();
			$('#iconLabel').text('Show Detail');
			isCollapsed = true;
		}

		// Store the state in local storage
		localStorage.setItem('isCollapsed', isCollapsed);
	});

	// Update the state when the checkbox is checked
	$('#checkbox').change(function() {
		localStorage.setItem('isCollapsed', $(this).is(':checked'));
	});
	// END ds_info controls

	checked_rows = []
	localStorage.setItem('filter', '99')
	var wdtask = false
	var tgntask = false
	var whgtask = false

	/*loggedin = {{ loggedin }}*/
	const check_column = loggedin == true ? {
		data: "properties.pid",
      	render: function (data, type, row) {
        	return `<input type="checkbox" name="addme" class="table-chk" data-id="${data}"/>`;
      	},
	} : {
		"data": "properties.pid",
		"visible": false
	}

	startSpinner("spinner_table", "drftable_list");
	startSpinner("spinner_detail", "row_detail");

	// task columns are inoperable in this public view
	table = $('#placetable').DataTable({
		/*dom:  "<'row small'<'col-sm-12 col-md-4'l>"+*/
		dom: "<'row small'<'col-sm-7'f>" +
			"<'col-sm-5'>>" +
			"<'row'<'col-sm-12'tr>>" +
			"<'row small'<'col-sm-12'p>>",
		// scrollY: 400,
		select: true,
		order: [
			[0, 'asc']
		],
		//pageLength: 250,
		//LengthMenu: [25, 50, 100],
		data: features,
		columns: [
			{
		      data: "properties.pid",
		      render: function (data, type, row) {
		        return `<a href="http://localhost:8000//api/db/?id=${data}" target="_blank">${data}</a>`;
		      }
		    },
		    {
		      data: "properties.title"
		    },
		    {
				data: "geometry",
	            render: function (data, type, row) {
	                if (data) {
	                    return `<img src="/static/images/geo_${data.type.toLowerCase().replace('multi','')}.svg" width=12/>`;
	                } else {
	                    return "<i>none</i>";
	                }
	            }
		    },
		    check_column
		],
		columnDefs: [
			/*{ className: "browse-task-col", "targets": [8,9,10] },*/
			/*{ orderable: false, "targets": [4, 5]},*/
			{
				orderable: false,
				"targets": [0, 2, 3]
			},
			{
				searchable: false,
				"targets": [0, 2, 3]
			}
			/*, {visible: false, "targets": [5]}*/
			/*, {visible: false, "targets": [0]}*/
		],
		rowId: 'properties.pid',
	    createdRow: function (row, data, dataIndex) {
	        // Attach temporal min and max properties as data attributes
	        $(row).attr('data-min', data.properties.min);
	        $(row).attr('data-max', data.properties.max);
			if (!data.geometry) {
		        $(row).addClass('no-geometry');
		    }
			if (data.properties.min === 'null' || data.properties.max === 'null') {
		        $(row).addClass('no-temporal');
		    }
	    },
	    initComplete: function(settings, json) {
	        adjustPageLength();
	    },
	    drawCallback: function(settings) {
			console.log('table drawn')
			spinner_table.stop()
			// recheck inputs in checked_rows
			if (checked_rows.length > 0) {
				for (i in checked_rows) {
					$('[data-id=' + checked_rows[i] + ']').prop('checked', true)
				}
				// make sure selection_status is visible
				$("#selection_status").show()
			}
			highlightFirstRow();
	    }
	})

	$("#addchecked").click(function() {
		console.log('clicked #addchecked')
		$("#addtocoll_popup").fadeIn()
	})

	$(".closer").click(function() {
		$("#addtocoll_popup").hide()
	})

	// help popups
	$(".help-matches").click(function() {
		page = $(this).data('id')
		console.log('help:', page)
		$('.selector').dialog('open');
	})
	$(".selector").dialog({
		resizable: false,
		autoOpen: false,
		height: 500,
		width: 700,
		title: "WHG Help",
		modal: true,
		buttons: {
			'Close': function() {
				console.log('close dialog');
				$(this).dialog('close');
			}
		},
		open: function(event, ui) {
			$('#helpme').load('/media/help/' + page + '.html')
		},
		show: {
			effect: "fade",
			duration: 400
		},
		hide: {
			effect: "fade",
			duration: 400
		}
	});
}

// activate all tooltips
$("[rel='tooltip']").tooltip();

function getPlace(pid) {
	console.log('getPlace()', pid);
    if (isNaN(pid)) {
        console.log('Invalid pid');
        return;
    }
	$.ajax({
		url: "/api/place/" + pid,
	}).done(function(data) {
		$("#detail").html(parsePlace(data))
		spinner_detail.stop()
		// events on detail items
		$('.ext').on('click', function(e) {
			e.preventDefault();
			str = $(this).text()
			//console.log('str (identifier)',str)-->
			// URL identifiers can be 'http*' or an authority prefix
			if (str.substring(0, 4).toLowerCase() == 'http') {
				url = str
			} else {
				var re = /(http|bnf|cerl|dbp|gn|gnd|gov|loc|pl|tgn|viaf|wd|wdlocal|whg|wp):(.*?)$/;
				url = base_urls[str.match(re)[1]] + str.match(re)[2]
				console.log('url', url)
			}
			window.open(url, '_blank');
		});
		$('.exttab').on('click', function(e) {
			e.preventDefault();
			id = $(this).data('id')
			console.log('id', id)
			var re = /(http|dbp|gn|tgn|wd|loc|viaf|aat):(.*?)$/;
			url = id.match(re)[1] == 'http' ? id : base_urls[id.match(re)[1]] + id.match(re)[2]
			console.log('url', url)
			window.open(url, '_blank')
		});
	});
	//spinner_detail.stop()-->
}

// single column
function parsePlace(data) {
	window.featdata = data

	function onlyUnique(array) {
		const map = new Map();
		const result = [];
		for (const item of array) {
			if (!map.has(item.identifier)) {
				map.set(item.identifier, true);
				result.push({
					identifier: item.identifier,
					type: item.type,
					aug: item.aug
				});
			}
		}
		return (result)
	}
	//timespan_arr = []-->
	//
	// TITLE 
	var descrip = '<p><b>Title</b>: <span id="row_title" class="larger text-danger">' + data.title + '</span>'
	//
	// NAME VARIANTS
	descrip += '<p class="scroll65"><b>Variants</b>: '
	for (var n in data.names) {
		let name = data.names[n]
		descrip += '<p>' + name.toponym != '' ? name.toponym + '; ' : ''
	}
	//
	// TYPES
	// may include sourceLabel:"" **OR** sourceLabels[{"label":"","lang":""},...]
	// console.log('data.types',data.types)
	//{"label":"","identifier":"aat:___","sourceLabels":[{"label":" ","lang":"en"}]}
	descrip += '</p><p><b>Types</b>: '
	var typeids = ''
	for (var t in data.types) {
		var str = ''
		var type = data.types[t]
		if ('sourceLabels' in type) {
			srclabels = type.sourceLabels
			for (l in srclabels) {
				label = srclabels[l]['label']
				str = label != '' ? label + '; ' : ''
			}
		} else if ('sourceLabel' in type) {
			str = type.sourceLabel != '' ? type.sourceLabel + '; ' : ''
		}
		if (type.label != '') {
			str += url_exttype(type) + ' '
		}
		typeids += str
	}
	descrip += typeids.replace(/(; $)/g, "") + '</p>'

	//
	// LINKS
	// 
	descrip += '<p class="mb-0"><b>Links</b>: '
	//close_count = added_count = related_count = 0
	var html = ''
	if (data.links.length > 0) {
		links = data.links
		links_arr = onlyUnique(data.links)
		/*console.log('distinct data.links',links_arr)*/
		for (l in links_arr) {
			descrip += url_extplace(links_arr[l].identifier)
		}
	} else {
		descrip += "<i class='small'>no links established yet</i>"
	}
	descrip += '</p>'

	//
	// RELATED
	//right=''-->
	if (data.related.length > 0) {
		parent = '<p class="mb-0"><b>Parent(s)</b>: ';
		related = '<p class="mb-0"><b>Related</b>: ';
		for (r in data.related) {
			rel = data.related[r]
			//console.log('rel',rel)-->
			if (rel.relation_type == 'gvp:broaderPartitive') {
				parent += '<span class="small h1em">' + rel.label
				parent += 'when' in rel && !('timespans' in rel.when) ?
					', ' + rel.when.start.in + '-' + rel.when.end.in :
					'when' in rel && ('timespans' in rel.when) ? ', ' +
					minmaxer(rel.when.timespans) : ''
				//rel.when.timespans : ''-->
				parent += '</span>; '
			} else {
				related += '<p class="small h1em">' + rel.label + ', ' + rel.when.start.in + '-' + rel.when.end.in + '</p>'
			}
		}
		descrip += parent.length > 39 ? parent : ''
		descrip += related.length > 37 ? related : ''
	}
	//
	// DESCRIPTIONS
	// TODO: link description to identifier URI if present
	if (data.descriptions.length > 0) {
		val = data.descriptions[0]['value'].substring(0, 300)
		descrip += '<p><b>Description</b>: ' + (val.startsWith('http') ? '<a href="' + val + '" target="_blank">Link</a>' : val) +
			' ... </p>'
		//'<br/><span class="small red-bold">('+data.descriptions[0]['identifier']+')</span>-->
	}
	//
	// CCODES
	//
	//if (data.ccodes.length > 0) {-->
	if (!!data.countries) {
		//console.log('data.countries',data.countries)-->
		descrip += '<p><b>Modern country bounds</b>: ' + data.countries.join(', ') + '</p>'
	}
	//
	// MINMAX
	//
	if (data.minmax && data.minmax.length > 0) {
		descrip += '<p><b>When</b>: earliest: ' + data.minmax[0] + '; latest: ' + data.minmax[1]
	}
	descrip += '</div>'
	return descrip
}
// builds link for external place record
function url_extplace(identifier) {
	// abbreviate links not in aliases.base_urls
	if (identifier.startsWith('http')) {
		let tag = identifier.replace(/.+\/\/|www.|\..+/g, '')
		link = '<a href="' + identifier + '" target="_blank">' + tag + '<i class="fas fa-external-link-alt linky"></i>,  </a>';
	} else {
		link = '<a href="" class="ext" data-target="#ext_site">' + identifier + '&nbsp;<i class="fas fa-external-link-alt linky"></i></a>, ';
	}
	return link
}

// builds link for external placetype record
function url_exttype(type) {
	const link = ' <a href="#" class="exttab" data-id=' + type.identifier +
		'>(' + type.label + ' <i class="fas fa-external-link-alt linky"></i>)</a>'
	return link
}

function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))-->
	starts = [];
	ends = []
	for (t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)-->
	minmax = [Math.max.apply(null, starts), Math.max.apply(null, ends)]
	return minmax
}

// spinners
function startSpinner(spinnerName, spinnerId) {
	const spin_opts = {
		scale: .5,
		top: '50%'
	}
    window[spinnerName] = new Spin.Spinner(spin_opts).spin();
    $("#" + spinnerId).append(window[spinnerName].el);
}
//*
