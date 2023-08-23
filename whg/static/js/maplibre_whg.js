maptilersdk.config.apiKey = mapParameters.mapTilerKey;

var mappy = new maptilersdk.Map({
	container: mapParameters.container,
	center: mapParameters.center,
	zoom: mapParameters.zoom,
	minZoom: mapParameters.minZoom,
	maxZoom: mapParameters.maxZoom,
	attributionControl: false,
	geolocateControl: false,
	navigationControl: false,
});

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

	fitPaddedBounds(mappy.getBounds());
	whgMap.style.opacity = 1;

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
		
	if (!!mapParameters.controls.temporal) {
		const datelineContainer = document.createElement('div');
		datelineContainer.id = 'dateline';
		document.getElementById('mapControls').appendChild(datelineContainer);
		const myDateline = new Dateline(dateline);
	};



	hilited = null;

	renderData(pageData);

	layer_list = ['outline', 'gl_active_point', 'gl_active_line', 'gl_active_poly']

	// popup generating events per layer
	// TODO: polygons?
	for (l in layer_list) {
		mappy.on('mouseenter', layer_list[l], function() {
			mappy.getCanvas().style.cursor = 'pointer';
		});

		// Change it back to a pointer when it leaves.
		mappy.on('mouseleave', layer_list[l], function() {
			mappy.getCanvas().style.cursor = '';
		});

		mappy.on('click', layer_list[l], function(e) {
			ftype = e.features[0].layer.type
			gtype = e.features[0].geometry.type
			geom = e.features[0].geometry
			coords = e.features[0].geometry.coordinates
			place = e.features[0]
			// console.log('geom, coords', geom, coords)
			if (ftype == 'point') {
				var coordinates = geom.coordinates.slice();
			} else if (ftype == 'line') {
				// could be simple linestring
				if (gtype == 'LineString') {
					len = Math.round(geom.coordinates.length / 2)
					var coordinates = geom.coordinates[len]
				} else {
					// MultiLineString
					segment = turf.lineString(coords[Math.round(coords.length / 2)])
					len = turf.length(segment)
					var coordinates = turf.along(segment, len / 2).geometry.coordinates
				}
			} else {
				var coordinates = turf.centroid(geom).geometry.coordinates
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
			new maplibregl.Popup()
				.setLngLat(coordinates)
				.setHTML('<b>' + title + '</b><br/>' +
					'<a href="javascript:getPlace(' + pid + ')">fetch info</a><br/>' +
					'start, end: ' + minmax)
				.addTo(mappy);
		})
	}
});

let mapPaddedBounds;

function getPaddedBounds() {
	const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
	const MapRect = document.getElementById('whgMap').getBoundingClientRect();
	const lowerLeftPixel = [MapRect.left - ControlsRect.left, MapRect.height - (MapRect.bottom - ControlsRect.bottom)];
	const topRightPixel = [ControlsRect.width + (MapRect.left - ControlsRect.left), MapRect.height - ControlsRect.height];
	// Convert pixel coordinates to map coordinates
	const lowerLeftLngLat = map.unproject(lowerLeftPixel);
	const topRightLngLat = map.unproject(topRightPixel);
	mapPaddedBounds = [lowerLeftLngLat, topRightLngLat];
}

function fitPaddedBounds(bounds) {
	const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
	const OverlaysRect = document.getElementById('mapOverlays').getBoundingClientRect();
	const padding = {
		top: ControlsRect.top - OverlaysRect.top,
		bottom: OverlaysRect.bottom - ControlsRect.bottom,
		left: ControlsRect.left - OverlaysRect.left,
		right: OverlaysRect.right - ControlsRect.right,
	};
	console.log('Map padding calculated:', padding);
	mappy.fitBounds(bounds, {
		padding,
		duration: 0
	});
}

// fetch and render
function renderData(dsid) {
	/*startMapSpinner()*/

	// clear any data layers and 'places' source
	if (!!mappy.getLayer('gl_active_point')) {
		mappy.removeLayer('gl_active_point')
		mappy.removeLayer('gl_active_line')
		mappy.removeLayer('gl_active_poly')
		mappy.removeLayer('outline')
		mappy.removeSource('places')
	}

	// fetch data
	$.get('/datasets/' + dsid + '/geojson', function(data) {
		features = data.collection.features
		/*console.log('data', data.collection)*/
		// get bounds w/turf
		envelope = turf.envelope(data.collection)
		range = data.minmax

		// add source 'places' w/retrieved data
		mappy.addSource('places', {
			'type': 'geojson',
			'data': data.collection
		})
		// The 'empty' source and layers need to be reset after a change of map style
		if (!mappy.getSource('empty')) mappy.addSource('empty', {
			type: 'geojson',
			data: {
				type: 'FeatureCollection',
				features: []
			}
		});
		for (let z = 4; z > 0; z--) {
			if (!mappy.getLayer('z-index-' + z)) {
				mappy.addLayer({
					id: 'z-index-' + z,
					type: 'symbol',
					source: 'empty'
				}, z == 4 ? '' : 'z-index-' + (z + 1)); //top
			}
		}

		// render to map
		// z-index points:4, poly-outlines:3. poly:2, lines:1       
		mappy.addLayer({
			'id': 'gl_active_point',
			'type': 'circle',
			'source': 'places',
			'paint': {
				'circle-opacity': 1,
				'circle-color': '#ff9900',
				'circle-radius': {
					stops: [
						[1, 2],
						[3, 3],
						[16, 10]
					]
				}
			},
			'filter': ['==', '$type', 'Point']
		}, 'z-index-4');

		// dashed outline for polygons
		mappy.addLayer({
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
		}, 'z-index-3');

		mappy.addLayer({
			'id': 'gl_active_poly',
			'type': 'fill',
			'source': 'places',
			'paint': {
				'fill-color': '#ddd',
				'fill-opacity': 0.3,
				'fill-outline-color': '#666'
			},
			'filter': ['==', '$type', 'Polygon']
		}, 'z-index-2');

		mappy.addLayer({
			'id': 'gl_active_line',
			'type': 'line',
			'source': 'places',
			'paint': {
				'line-color': '#336699',
				'line-width': {
					stops: [
						[1, 1],
						[4, 2],
						[16, 4]
					]
				}
			},
			'filter': ['==', '$type', 'LineString']
		}, 'z-index-1');

		fitPaddedBounds(envelope.bbox);
		/*spinner_map.stop()*/

	}) // get
} //highlightFeatureGL