import datasetLayers from './mapLayerStyles';
import {attributionString, arrayColors, colorTable, startSpinner} from './utilities';
import { filteredLayer } from './mapFilters';
import { scrollToRowByProperty, clearFilters } from './tableFunctions';
import { popupFeatureHTML } from './getPlace.js';
import { mappy } from './mapAndTable';

let mapParams;

export function addMapSource(ds) {
	mappy.addSource(ds.id.toString(), {
		'type': 'geojson',
		'data': ds,
		'attribution': attributionString(ds),
	});
}

export function addMapLayer(layer, ds) {
	const modifiedLayer = {
		...layer
	};
	modifiedLayer.id = `${layer.id}_${ds.id}`;
	modifiedLayer.source = ds.id.toString();
	mappy.addLayer(filteredLayer(modifiedLayer));
	if (!!ds.relations && layer.id == 'gl_active_point') {
		let circleColors = arrayColors(ds.relations);
		// colorTable(circleColors, '#coll_detail');
		colorTable(circleColors, '#mapControls');
		mappy.setPaintProperty(modifiedLayer.id, 'circle-color', [
			'match',
			['get', 'relation'],
			...circleColors,
			'#ccc',
		]);
		mappy.setPaintProperty(modifiedLayer.id, 'circle-stroke-color', [
			'match',
			['get', 'relation'],
			...circleColors,
			'#ccc',
		]);
	}
}

export function updatePadding() {
	const ControlsRect = mapParams.ControlsRectEl.getBoundingClientRect();
	const MapRect = mapParams.MapRectEl.getBoundingClientRect();
	mappy.setPadding({
		top: ControlsRect.top - MapRect.top - mapParams.ControlsRectMargin,
		bottom: MapRect.bottom - ControlsRect.bottom - mapParams.ControlsRectMargin,
		left: ControlsRect.left - MapRect.left - mapParams.ControlsRectMargin,
		right: MapRect.right - ControlsRect.right - mapParams.ControlsRectMargin,
	});
}

function updateBounds() {
	const ControlsRect = mapParams.ControlsRectEl.getBoundingClientRect();
	const MapRect = mapParams.MapRectEl.getBoundingClientRect();
	const centerX = -mapParams.MapRectBorder + ControlsRect.left - MapRect.left + ControlsRect.width / 2;
	const centerY = -mapParams.MapRectBorder + ControlsRect.top - MapRect.top + ControlsRect.height / 2;
	const pseudoCenter = mapParams.mappy.unproject([centerX, centerY]);
	window.mapBounds = {
		'center': pseudoCenter
	}
	//console.log('window.mapBounds updated:', window.mapBounds);
}

// Control positioning of map, clear of overlays
export function recenterMap(duration) {
	duration = duration == 'lazy' ? 1000 : 0 // Set duration of movement
	window.blockBoundsUpdate = true;
	// mappy.showPadding = true; // Used for debugging - draws coloured lines to indicate padding
	if (window.mapBounds) {
		if (Array.isArray(window.mapBounds) || !window.mapBounds.hasOwnProperty('center')) { // mapBounds might be a coordinate pair object returned by mappy.getBounds();
			mappy.fitBounds(window.mapBounds, {
				duration: duration
			});
		} else { // mapBounds has been set based on a center point and zoom
			mappy.flyTo({
				...window.mapBounds,
				duration: duration
			})
		}
	}
}

export function initObservers() {

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
		recenterMap(false);
	});

	// Recenter map whenever its viewport changes size
	resizeObserver.observe(mapParams.ControlsRectEl);
	resizeObserver.observe(mapParams.MapRectEl);
	updatePadding();

	mappy.on('zoomend', function() { // Triggered by `flyTo` and `fitBounds` - must be blocked to prevent misalignment 
		if (window.blockBoundsUpdate) {
			window.blockBoundsUpdate = false;
			//console.log('blockBoundsUpdate released.');
		} else {
			updateBounds();
		}
	});
	mappy.on('dragend', function() {
		updateBounds();
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

	// Initialise Download link listener
	$(".a-dl, .a-dl-celery").click(function(e) {
		e.preventDefault();
		let dsid = $(this).data('id');
		let collid = $(this).data('collid');
		let urly = '/datasets/dlcelery/'
		$.ajax({
			type: 'POST',
			url: urly,
			data: {
				"format": 'lpf',
				"dsid": dsid,
				"collid": collid,
				"csrfmiddlewaretoken": window.csrfToken
			},
			datatype: 'json',
			success: function(response) {
				// window.spinner_download = startSpinner("metadata");
				// TODO: window.spinner_download.stop() not yet implemented anywhere?
				let task_id = response.task_id
				var progressUrl = "/celery-progress/" + task_id + "/";
				CeleryProgressBar.initProgressBar(progressUrl, {
					pollingInterval: 500,
					onResult: customResult,
				})
			}
		})
	})

			// called from a-dl click()

	// TODO: Collection download event handlers
	$(".btn-cancel").click(function() {
		$("#downloadModal").modal('hide')
	})
	let clearEl = function(el) {
		$("#progress-bar").fadeOut()
		el.html('')
	}
}

let activePopup;
export function initPopups(table) {

	function clearPopup(preserveCursor = false) {
		if (activePopup) {
			if (activePopup.featureHighlight !== false) {
				mappy.setFeatureState(activePopup.featureHighlight, { highlight: false });
			}
			activePopup.remove();
			activePopup = null;
			if (!preserveCursor) mappy.getCanvas().style.cursor = '';
		}
	}

	mappy.on('mousemove', function(e) {
		const features = mappy.queryRenderedFeatures(e.point);

		if (features.length > 0) {
			const topFeature = features[0]; // Handle only the top-most feature
			const topLayerId = topFeature.layer.id;

			// Check if the top feature's layer id starts with the id of any layer in datasetLayers
			const isTopFeatureInDatasetLayer = datasetLayers.some(layer => topLayerId.startsWith(layer.id));

			if (isTopFeatureInDatasetLayer) {
				mappy.getCanvas().style.cursor = 'pointer';

		        if (!activePopup || activePopup.pid !== topFeature.properties.pid) {
		          // If there is no activePopup or it's a different feature, create a new one ...
		          if (activePopup) {
		            clearPopup(true);
		          }
		          activePopup = new maptilersdk.Popup({
		            closeButton: false,
		          })
		            .setLngLat(e.lngLat)
		            .setHTML(popupFeatureHTML(topFeature))
		            .addTo(mappy);
		          activePopup.pid = topFeature.properties.pid;
		          activePopup.featureHighlight = { source: topFeature.source, id: topFeature.id };
		          if (!!window.highlightedFeatureIndex && window.highlightedFeatureIndex.id === activePopup.featureHighlight.id && window.highlightedFeatureIndex.source === activePopup.featureHighlight.source) {
					  activePopup.featureHighlight = false;
				  }
				  else {
		          	  mappy.setFeatureState(activePopup.featureHighlight, { highlight: true });
				  }
		        } else {
		          // ... otherwise just update its position
		          activePopup.setLngLat(e.lngLat);
		        }

			} else {
				clearPopup();
			}
		} else {
			clearPopup();
		}
	});

	mappy.on('click', function() {
		if (activePopup && activePopup.pid) {
			let savedPID = activePopup.pid;
			clearPopup();
			table.search('').draw();
			scrollToRowByProperty(table, 'pid', savedPID);
		}
	});
}

export function listSourcesAndLayers() {
	const style = mappy.getStyle();
	const sources = style.sources;
	console.log('Sources:', Object.keys(sources));
	const layers = style.layers;
	console.log('Layers:', layers.map(layer => layer.id));
}