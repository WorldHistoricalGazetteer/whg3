maptilersdk.Map.prototype.fitViewport = function (bbox) {
	// This function addresses an apparent bug with flyTo and fitBounds in MapLibre/Maptiler,
	// which crash and/or fail to center correctly with large mapPadding values.
	const mapContainer = this.getContainer();
	const mapContainerRect = mapContainer.getBoundingClientRect();
	const mapControls = mapContainer.querySelector('.maplibregl-control-container');
	const mapControlsRect = mapControls.getBoundingClientRect();
	const mapControlsRectMargin = parseFloat(getComputedStyle(mapControls).marginTop);
	
	const padding = 10; // Apply equal padding on all sides within viewport
	
	const bounds = [[bbox[0], bbox[1]], [bbox[2], bbox[3]]];
	const sw = this.project(bounds[0]);
	const ne = this.project(bounds[1]);
	let zoom = Math.log2(
		Math.min(
			(mapControlsRect.width - 2 * padding) / (ne.x - sw.x), 
			(mapControlsRect.height- 2 * padding) / (sw.y - ne.y))
		) + this.getZoom();
	zoom = Math.min(zoom, this.getMaxZoom());
	zoom = Math.max(zoom, this.getMinZoom());
	
	const viewportPadding = {
		top: Math.round(mapControlsRect.top - mapContainerRect.top - mapControlsRectMargin),
		bottom: Math.round(mapContainerRect.bottom - mapControlsRect.bottom - mapControlsRectMargin),
		left: Math.round(mapControlsRect.left - mapContainerRect.left - mapControlsRectMargin),
		right: Math.round(mapContainerRect.right - mapControlsRect.right - mapControlsRectMargin),
	};
	
	this.flyTo({
		center: [
			(bbox[0] + bbox[2]) / 2,
			(bbox[1] + bbox[3]) / 2
		],
		zoom: zoom,
		padding: viewportPadding,
		duration: 1000,
	});
};
