import datasetLayers from './mapLayerStyles';
import { attributionString } from './utilities';
import { filteredLayer } from './mapFilters';
let blockMoveend = false;

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

// Control positioning of map, clear of overlays
export function recenterMap(mappy, duration) {
	duration = duration ==  'lazy' ? 1000 : 0 // Set duration of movement
	const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
	const OverlaysRect = document.getElementById('mapOverlays').getBoundingClientRect();
	window.mapPadding = {
		top: ControlsRect.top - OverlaysRect.top,
		bottom: OverlaysRect.bottom - ControlsRect.bottom,
		left: ControlsRect.left - OverlaysRect.left,
		right: OverlaysRect.right - ControlsRect.right,
	};
	
	blockMoveend = true;
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
	// console.log('mapPadding calculated:', window.mapBounds, window.mapPadding);
}

export function initObservers(mappy) {
	const resizeObserver = new ResizeObserver(function(){ recenterMap(mappy) });
	// Recenter map whenever its viewport changes size
	resizeObserver.observe(document.getElementById('mapControls'));
	resizeObserver.observe(document.getElementById('mapOverlays'));
	
	mappy.on('moveend', function() {
		if (blockMoveend) {
			blockMoveend = false;
		}
		else {
			const MapRectBorder = 1;
			const ControlsRect = document.getElementById('mapControls').getBoundingClientRect();
			const MapRect = document.querySelector('div.maplibregl-map').getBoundingClientRect();
			const centerX = - MapRectBorder + ControlsRect.left - MapRect.left + ControlsRect.width / 2;
			const centerY = - MapRectBorder + ControlsRect.top - MapRect.top + ControlsRect.height / 2;
			const pseudoCenter = mappy.unproject([centerX, centerY]);
			window.mapBounds = {
				'center': pseudoCenter
			}
			console.log('window.mapBounds updated:',window.mapBounds);
		}
		
	});
	
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