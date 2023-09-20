import datasetLayers from './mapLayerStyles';
import { attributionString } from './utilities';
import { filteredLayer } from './mapFilters';

export function addMapSources(mappy, data) {
		
	mappy.addSource('places', {
		'type': 'geojson',
		'data': data,
		'attribution': attributionString(data),
	})

	datasetLayers.forEach(function(layer) {
		mappy.addLayer(filteredLayer(layer));
	});
	
}

let mapParams;
	
export function updatePadding() {
	const ControlsRect = mapParams.ControlsRectEl.getBoundingClientRect();
	const MapRect = mapParams.MapRectEl.getBoundingClientRect();
	window.mapPadding = {
		top: ControlsRect.top - MapRect.top - mapParams.ControlsRectMargin,
		bottom: MapRect.bottom - ControlsRect.bottom - mapParams.ControlsRectMargin,
		left: ControlsRect.left - MapRect.left - mapParams.ControlsRectMargin,
		right: MapRect.right - ControlsRect.right - mapParams.ControlsRectMargin,
	};
	console.log('mapPadding recalculated:', window.mapPadding);
}

function updateBounds() {
	const ControlsRect = mapParams.ControlsRectEl.getBoundingClientRect();
	const MapRect = mapParams.MapRectEl.getBoundingClientRect();
	const centerX = - mapParams.MapRectBorder + ControlsRect.left - MapRect.left + ControlsRect.width / 2;
	const centerY = - mapParams.MapRectBorder + ControlsRect.top - MapRect.top + ControlsRect.height / 2;
	const pseudoCenter = mapParams.mappy.unproject([centerX, centerY]);
	window.mapBounds = {
		'center': pseudoCenter
	}
	console.log('window.mapBounds updated:', window.mapBounds);
}

// Control positioning of map, clear of overlays
export function recenterMap(mappy, duration) {
	duration = duration ==  'lazy' ? 1000 : 0 // Set duration of movement
	window.blockBoundsUpdate = true;
	
	if (window.mapBounds) {
		if (Array.isArray(window.mapBounds) || !window.mapBounds.hasOwnProperty('center')) { // mapBounds might be a coordinate pair object returned by mappy.getBounds();
			mappy.fitBounds(window.mapBounds, {
				padding: window.mapPadding,
				duration: duration
			});
		} else { // mapBounds has been set based on a center point and zoom
			mappy.flyTo({
				...window.mapBounds,
				padding: window.mapPadding,
				duration: duration
			})
		}
	}
}

export function initObservers(mappy) {
	
	mapParams = {
		mappy: mappy,
		ControlsRectEl: document.getElementById('mapControls'),
		MapRectEl: document.querySelector('div.maplibregl-map'),
		ControlsRectMargin: 4,
		MapRectBorder: 1
	}
	
	window.blockBoundsUpdate = false;
	const resizeObserver = new ResizeObserver(function() { 
		updatePadding();
		recenterMap(mappy);
	});

	// Recenter map whenever its viewport changes size
	resizeObserver.observe(mapParams.ControlsRectEl);
	resizeObserver.observe(mapParams.MapRectEl);
	
	mappy.on('zoomend', function() { // Triggered by `flyTo` and `fitBounds` - must be blocked to prevent misalignment 
		if (window.blockBoundsUpdate) {
			window.blockBoundsUpdate = false;
			console.log('blockBoundsUpdate released.');
		}
		else {
			updateBounds();
		}
	});
	mappy.on('dragend', function() { updateBounds(); });
	
}

export function initOverlays(whgMap) {
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
}

export function initPopups(mappy, activePopup, table) {

	datasetLayers.forEach(function(layer) {

		mappy.on('mouseenter', layer.id, function(e) {
			mappy.getCanvas().style.cursor = 'pointer';

			var pid = e.features[0].properties.pid;
			var title = e.features[0].properties.title;
			var min = e.features[0].properties.min;
			var max = e.features[0].properties.max;

			if (activePopup) {
				activePopup.remove();
			}
			activePopup = new maptilersdk.Popup({
					closeButton: false
				})
				.setLngLat(e.lngLat)
				.setHTML('<b>' + title + '</b><br/>' +
					'Temporality: ' + (min ? min : '?') + '/' + (max ? max : '?') + '<br/>' +
					'Click to focus'
				)
				.addTo(mappy);
			activePopup.pid = pid;
		});

		mappy.on('mousemove', layer.id, function(e) {
			if (activePopup) {
				activePopup.setLngLat(e.lngLat);
			}
		});

		mappy.on('mouseleave', layer.id, function() {
			mappy.getCanvas().style.cursor = '';
			if (activePopup) {
				activePopup.remove();
			}

		});

		mappy.on('click', layer.id, function(e) {

			var pid;
			if (activePopup && activePopup.pid) {
				pid = activePopup.pid;
				activePopup.remove();
			} else pid = e.features[0].properties.pid;

			// Search for the row within the sorted and filtered view
			var pageInfo = table.page.info();
			var rowPosition = -1;
			var rows = table.rows({
				search: 'applied',
				order: 'current'
			}).nodes();
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

	});
}