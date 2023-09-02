// /whg/webpack/js/maplibre_whg.js

//import'./gis_resources';
import { envelope, lineString, length, along, centroid } from './6.5.0_turf.min.js'
import '../css/maplibre_whg.css';
import '../css/dateline.css';
import Dateline from './dateline';
import { dateRangeChanged, getPlace, initialiseTable } from './ds_places_new';

maptilersdk.config.apiKey = mapParameters.mapTilerKey;

export var mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	attributionControl: false,
	geolocateControl: false,
	navigationControl: false,
});

export let mapPadding;
export let mapBounds;
export let features;
export let dateline = null;
let datelineContainer = null;

if (!!mapParameters.controls.navigation) map.addControl(new maptilersdk.NavigationControl(), 'top-left');

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
	compact: true,
	customAttribution: 'WHG'
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
			}
			else { // mapBounds has been set based on a center point and zoom
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

	// popup generating events per layer
	// TODO: polygons?
	for (var l in layer_list) {
		mappy.on('mouseenter', layer_list[l], function() {
			mappy.getCanvas().style.cursor = 'pointer';
		});

		// Change it back to a pointer when it leaves.
		mappy.on('mouseleave', layer_list[l], function() {
			mappy.getCanvas().style.cursor = '';
		});

		mappy.on('click', layer_list[l], function(e) {
			const ftype = e.features[0].layer.type
			const gtype = e.features[0].geometry.type
			const geom = e.features[0].geometry
			const coords = e.features[0].geometry.coordinates
			const place = e.features[0]
			// console.log('geom, coords', geom, coords)
			if (ftype == 'point') {
				var coordinates = geom.coordinates.slice();
			} else if (ftype == 'line') {
				// could be simple linestring
				if (gtype == 'LineString') {
					const len = Math.round(geom.coordinates.length / 2)
					var coordinates = geom.coordinates[len]
				} else {
					// MultiLineString
					const segment = lineString(coords[Math.round(coords.length / 2)])
					const len = length(segment)
					var coordinates = along(segment, len / 2).geometry.coordinates
				}
			} else {
				var coordinates = centroid(geom).geometry.coordinates
			}
			var pid = e.features[0].properties.pid;
			var title = e.features[0].properties.title;
			var src_id = e.features[0].properties.src_id;
			var minmax = e.features[0].properties.minmax;
			var fc = e.features[0].properties.fclasses;

			while (Math.abs(e.lngLat.lng - coordinates[0]) > 180) {
				coordinates[0] += e.lngLat.lng > coordinates[0] ? 360 : -360;
			}

			// popup
			new maptilersdk.Popup()
				.setLngLat(coordinates)
				.setHTML('<b>' + title + '</b><br/>' +
					// Cannot use href="javascript:<function>" in module. EventListener added to class instead.
			        '<a href="#" class="fetch-info-link" data-pid="' + pid + '">fetch info</a><br/>' +
			        'start, end: ' + minmax)
				.addTo(mappy);
		})
	}
	
	document.addEventListener('click', function(event) {
	    if (event.target && event.target.classList.contains('fetch-info-link')) {
	        const pid = event.target.getAttribute('data-pid');
	        getPlace(pid);
	        event.preventDefault();
	    }
	});
	
});

export const datasetLayers = [
	{
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
	            ['boolean', ['feature-state', 'highlight'], false], 'rgba(0,128,0)', 
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
			// 'fill-outline-color': '#666'
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
			'circle-stroke-color': 'red',
			'circle-stroke-opacity': .8,
			'circle-stroke-width': [ // Simulate larger radius - zoom-based radius cannot operate together with feature-state switching
	            'case',
	            ['boolean', ['feature-state', 'highlight'], false], 5,
	            0
	        ],
			'circle-radius': [
	            'interpolate',
	            ['linear'],
	            ['zoom'],
	            0, 1, // zoom, radius
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
	if ( $('.range_container.expanded').length > 0) { // Is dateline active?
		const modifiedLayer = ({... layer});
		const existingFilter = modifiedLayer.filter;
		modifiedLayer.filter = [
            'all',
            existingFilter,
            ['has', 'max'],
            ['has', 'min'],
            ['>=', 'max', dateline.fromValue],
            ['<=', 'min', dateline.toValue]
        ];
        return modifiedLayer;
	}
	else return layer;
}

// fetch and render
function renderData(dsid) {
	/*startMapSpinner()*/
		
	// clear any data layers and 'places' source
	datasetLayers.forEach(function(layer, z){
		if (!!mappy.getLayer(layer.id)) mappy.removeLayer(layer.id);
		if (!!mappy.getLayer('z-index-' + z)) mappy.removeLayer('z-index-' + z);
	});
	if (!!mappy.getSource('places')) mappy.removeSource('places')

	// fetch data
	$.get('/datasets/' + dsid + '/geojson', function(data) {
		features = data.collection.features;
		initialiseTable();
		// console.log('data', data.collection)
		// get bounds w/turf
		const dcEnvelope = envelope(data.collection)
		// range = data.minmax

		// add source 'places' w/retrieved data
		mappy.addSource('places', {
			'type': 'geojson',
			'data': data.collection,
			'generateId': true // Required because otherwise-inserted ids are not recognised by style logic
		})		
		
		// The 'empty' source and layers need to be reset after a change of map style
		if (!mappy.getSource('empty')) mappy.addSource('empty', {
			type: 'geojson',
			data: {
				type: 'FeatureCollection',
				features: []
			}
		});
		
		datasetLayers.forEach(function(layer, z){
			mappy.addLayer( filteredLayer(layer) );
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
