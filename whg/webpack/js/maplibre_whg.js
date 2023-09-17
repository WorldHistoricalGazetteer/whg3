// /whg/webpack/js/maplibre_whg.js

import {
	envelope,
	lineString,
	length,
	along,
	centroid
} from './6.5.0_turf.min.js'
import '../css/maplibre_whg.css';
import '../css/dateline.css';
import '../css/maplibre-gl-export.css';
import Dateline from './dateline';
import generateMapImage from './saveMapImage';
import {
	dateRangeChanged,
	getPlace,
	initialiseTable
} from './ds_places_new';

maptilersdk.config.apiKey = mapParameters.mapTilerKey;

export var mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	attributionControl: false,
	geolocateControl: false,
	navigationControl: false
});

export let mapPadding;
export let mapBounds;
export let features;
export let dateline = null;
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

export const datasetLayers = [{
		'id': 'gl_active_line',
		'type': 'line',
		'source': 'places',
		'paint': {
			'line-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'green',
				'lightgreen'
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
				['boolean', ['feature-state', 'highlight'], false], 'rgb(0,128,0)',
				'#ddd'
			],
			'fill-opacity': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], .8,
				.3
			],
			'fill-outline-color': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], 'red',
				'#666'
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
			'line-color': '#999',
			'line-width': 1,
			'line-dasharray': [4, 2],
			'line-opacity': 0.5,
		},
		'filter': ['==', '$type', 'Polygon']
	},
	{
		'id': 'gl_active_point',
		'type': 'circle',
		'source': 'places',
		'paint': {
			'circle-opacity': [
				'case',
				['boolean', ['feature-state', 'highlight'], false], .8,
				.5
			],
			'circle-stroke-color': [
	            'case',
				['boolean', ['feature-state', 'highlight'], false], 'red',			
				'orange'
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
				['boolean', ['feature-state', 'highlight'], false], 'red',		
				'orange'
	        ],
		},
		'filter': ['==', '$type', 'Point'],
	}
]

export function filteredLayer(layer) {
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
	/*startMapSpinner()*/

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
		// get bounds w/turf
		const dcEnvelope = envelope(data)
		// range = data.minmax
		
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

		mapBounds = dcEnvelope.bbox; // Used if map is resized
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

import './ds_places_new.js';