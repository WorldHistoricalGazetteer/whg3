// whg_maplibre.js

import { Map, MapStyle, config, NavigationControl, AttributionControl } from '/webpack/node_modules/@maptiler/sdk/dist/maptiler-sdk.mjs';
import '@maptiler/sdk/dist/maptiler-sdk.css';
import '../css/maplibre-common.css';
import '../css/style-control.css';

const custom_styles = {
    'ne_global': {
        version: 8,
        sources: {
            basemap: {
                type: 'raster',
                tiles: [
                    `https://a.tiles.mapbox.com/v4/kgeographer.ne_global/{z}/{x}/{y}.png?access_token=${process.env.MAPBOX_TOKEN_WHG}`,
                    `https://b.tiles.mapbox.com/v4/kgeographer.ne_global/{z}/{x}/{y}.png?access_token=${process.env.MAPBOX_TOKEN_WHG}`
                ],
                tileSize: 256,
            },
        },
        layers: [{
            id: 'basemap',
            type: 'raster',
            source: 'basemap',
        }]        
    },
}

function convertStyle(style) {
	
	console.log(style);  
  	if (Array.isArray(style)) {
		console.log(`Setting style from array: ${style}`);
		let styleCode = style[0].split('.');
		style = MapStyle[styleCode[0]][styleCode[1]];
  	}
  	else if (typeof style === 'string') {
	  	console.log(`Setting style: ${style}`);
	  	style = custom_styles[style];
	}	
  	else if (typeof style === 'object') {
	  	console.log('Setting style:', style);
	}
	else {
		console.log('Unable to set style.', style);
	}
	return style;
	
}

// Override the setStyle method to handle style arrays
const originalSetStyle = Map.prototype.setStyle;
Map.prototype.setStyle = function (style) {
	return originalSetStyle.call(this, convertStyle(style));
};

function generateMapImage(map, dpi = 300, fileName = 'WHG_Map') {

	// Create a modal dialog for copyright attribution and acknowledgment
	const modal = $('<div id="map-download-dialog" title="Map Attribution"></div>');
	const injunctionText = $('<div id="injunction-text" class="injunction-text">The following attribution must be displayed together with any use of this map image:</div>');
	const attributionText = $('<div id="attribution-text" class="attribution-text"></div>');
	const downloadButton = $('<button id="download" style="display: none;" disabled>...rendering...</button>');
	const copyAttributionButton = $('<button id="copy-attribution">Acknowledge and Copy Attribution</button>');
	const cancelButton = $('<button id="cancel">Cancel</button>');

	// Add the missing paragraph
	modal.append(injunctionText);
	modal.append(attributionText);
	modal.append(copyAttributionButton);
	modal.append(downloadButton);
	modal.append(cancelButton);

	// Create a dialog with the modal content
	modal.dialog({
		autoOpen: false,
		appendTo: '#map',
		modal: true,
		width: 'auto',
		buttons: [],
		closeOnEscape: false,
		open: function() {
			const style = map.getStyle();
			if (style && style.sources) {
				const sources = style.sources;
				const attributions = [];
				Object.keys(sources).forEach((sourceName) => {
					const source = sources[sourceName];
					if (source.attribution) {
						const tempElement = document.createElement('div');
						tempElement.innerHTML = source.attribution;
						const displayedText = tempElement.textContent;
						attributions.push(displayedText);
					}
				});
				const fullAttributionText = attributions.join('\n');
				attributionText.text(fullAttributionText);
	
				new ClipboardJS(copyAttributionButton[0], {
				  text: function(trigger) {
				    return $('#map-download-dialog #attribution-text').text();
				  },
	    		  container: document.getElementById('map-download-dialog')
				}).on('success', function(e) {
				  console.log('Attribution text copied to clipboard.');
				  downloadButton.show();
				}).on('error', function(e) {
				  console.error('Unable to copy attribution text: ', e);
				});
			}
		},
	});

	const originalCanvas = map.getCanvas();
	const width = originalCanvas.width;
	const height = originalCanvas.height;

	// Store the actual devicePixelRatio
	const actualPixelRatio = window.devicePixelRatio;
	// Set the devicePixelRatio for higher DPI rendering
	Object.defineProperty(window, 'devicePixelRatio', {
		get: function() {
			return dpi / 96;
		},
	});
	console.log(actualPixelRatio, window.devicePixelRatio, map.getStyle());

	// Create a hidden container for rendering the map
	const originalMapContainer = originalCanvas.parentNode;
	const container = document.createElement('div');
	container.id = 'map-render-container';
	container.style.width = width + 'px';
	container.style.height = height + 'px';
	originalMapContainer.appendChild(container);

	// Create a map renderer
	const renderMap = new Map({
		container: container,
		style: map.getStyle(),
		center: map.getCenter(),
		zoom: map.getZoom(),
		bearing: map.getBearing(),
		pitch: map.getPitch(),
		interactive: false,
		preserveDrawingBuffer: true,
		fadeDuration: 0,
		attributionControl: false,
		transformRequest: map._requestManager._transformRequestFn,
	});

	renderMap.once('idle', () => {
		downloadButton.prop('disabled', false).text('Download');
	});

	// Download button event handler
	downloadButton.on('click', () => {
		const canvas = renderMap.getCanvas();
		const imageFileName = `${fileName}.png`;

		// Create a download link for the image
		const a = $('<a>');
		a.prop('href', canvas.toDataURL());
		a.prop('download', imageFileName);
		a[0].click();
		a.remove();

		cleanUp();
	});

	function cleanUp() {
		//renderMap.remove();
		container.remove();
			  Object.defineProperty(window, 'devicePixelRatio', {
			    get: function () {
			      return actualPixelRatio;
			    },
			  });
		modal.dialog('close');
		modal.remove();

	}

	// Cancel button event handler
	cancelButton.on('click', () => {
		cleanUp();
	});

	// Open the dialog
	modal.dialog('open');
}

class downloadMapControl {

	constructor(mapInstance) {
		this._map = mapInstance;
	}
	
    onAdd() {
        this._container = document.createElement('div');
        this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-download';
        //this._container.textContent = 'Download image';

        const downloadButton = document.createElement('button');
        downloadButton.type = 'button';
        downloadButton.className = 'download-map-button';
        downloadButton.setAttribute('aria-label', 'Download map image');
        downloadButton.setAttribute('title', 'Download map image');

        const iconSpan = document.createElement('span');
        iconSpan.className = 'maplibregl-ctrl-icon';
        iconSpan.setAttribute('aria-hidden', 'true');

        downloadButton.appendChild(iconSpan);
        this._container.appendChild(downloadButton);

        downloadButton.addEventListener('click', () => {
            generateMapImage(this._map);
        });

        return this._container;
    }
}

class acmeStyleControl {

	constructor(mapInstance, style) {
		this._map = mapInstance;
		this.styleFilter = style
	}

	onAdd() {
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
		this._container.textContent = 'Basemap';
		this._container.innerHTML =
			'<button type="button" class="style-button" aria-label="Change basemap style" title="Change basemap style">' +
			'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
			'</button>';
		this._container.querySelector('.style-button').addEventListener('click', this._onClick.bind(this));
		const currentStyle = this._map.getStyle();
		this.baseStyle = {};
		this.baseStyle.sources = Object.keys(currentStyle.sources);
		this.baseStyle.layers = currentStyle.layers.map((layer) => layer.id);
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
			const styleFilterValues = this.styleFilter.map(value => value.split('.')[0]);
			for (const group of Object.values(MapStyle)) {
				// Check if the group.id is in the styleFilter array
				if (this.styleFilter.length == 0 || styleFilterValues.includes(group.id)) {
					const groupItem = document.createElement('li');
					groupItem.textContent = group.name;
					groupItem.className = 'group-item';
					const variantList = document.createElement('ul');
					variantList.className = 'variant-list';
					for (const orderedVariant of group.orderedVariants) {
						const datasetValue = group.id + '.' + orderedVariant.variantType;
						if (this.styleFilter.length == 0 || this.styleFilter.includes(datasetValue)) {
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
		const style_code = variantValue.split(".");
		console.log('Selected variant: ', variantValue, MapStyle[style_code[0]][style_code[1]]);
		this._map.setStyle([variantValue], {
			transformStyle: (previousStyle, nextStyle) => { // Identify sources and layers that were added to the baseStyle
				const newSources = {
					...nextStyle.sources
				};
				Object.keys(previousStyle.sources).forEach((sourceId) => {
					if (!this.baseStyle.sources.includes(sourceId)) {
						newSources[sourceId] = previousStyle.sources[sourceId];
					}
				});
				const additionalLayers = previousStyle.layers.filter((layer) => !this.baseStyle.layers.includes(layer.id));
				this.baseStyle.sources = Object.keys(nextStyle.sources); // Update baseStyle record
				this.baseStyle.layers = nextStyle.layers.map((layer) => layer.id);
				return {
					...nextStyle,
					sources: newSources,
					layers: [...nextStyle.layers, ...additionalLayers],
				};
			}
		});

		const styleList = document.getElementById('mapStyleList');
		if (styleList) {
			styleList.classList.remove('show');
		}
	}
}

Map.prototype.reset = function () {
	this.flyTo({
		center: this.initOptions.center,
		zoom: this.initOptions.zoom,
        speed: .5,
    });
}

Map.prototype.fitViewport = function (bbox) {
	// This function addresses an apparent bug with flyTo and fitBounds in MapLibre/Maptiler,
	// which crash and/or fail to center correctly with large mapPadding values.
	const mapContainer = this.getContainer();
	const mapContainerRect = mapContainer.getBoundingClientRect();
	const mapControls = mapContainer.querySelector('.maplibregl-control-container');
	mapControls.style.height = '100%';
	const mapControlsRect = mapControls.getBoundingClientRect();
	const mapControlsRectMargin = parseFloat(getComputedStyle(mapControls).marginTop);
	
	const padding = 10; // Apply equal padding on all sides within viewport
	
	const bounds = [[bbox[0], bbox[1]], [bbox[2], bbox[3]]];
	const sw = this.project(bounds[0]);
	const ne = this.project(bounds[1]);
	let zoom = Math.log2( // Returns Infinity for bbox(Point)
		Math.min(
			(mapControlsRect.width - 2 * padding) / (ne.x - sw.x), 
			(mapControlsRect.height- 2 * padding) / (sw.y - ne.y))
		) + this.getZoom();
	zoom = isNaN(zoom) ? this.getMaxZoom() : Math.min(zoom, this.getMaxZoom());
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

class CustomAttributionControl extends AttributionControl {
    constructor(options) {
        super(options);
        this.autoClose = options.autoClose !== false;
    }
    onAdd(map) {
        const container = super.onAdd(map);
        // Automatically close the AttributionControl if autoClose is enabled
        if (this.autoClose) {
            const attributionButton = container.querySelector('.maplibregl-ctrl-attrib-button');
            if (attributionButton) {
                attributionButton.dispatchEvent(new MouseEvent('click', {
                    bubbles: true,
                    cancelable: true,
                    view: window
                }));
                container.classList.add('fade-in');
            }
        }
        return container;
    }
}

const originalMapConstructor = Map;
Map = function (options = {}) {
		
    const defaultOptions = {
        container: 'map',
        style: 'ne_global', // ['DATAVIZ.DEFAULT'], or with style switcher ['DATAVIZ.DEFAULT', 'OUTDOOR.DEFAULT']
        zoom: 0.2,
        center: [9.2, 33],
        minZoom: 0.1,
        maxZoom: 6,
        attributionControl: false, // {position: 'bottom-right', autoClose: true},
        geolocateControl: false,
        navigationControl: false, // {position: 'top-right', showCompass: false},
        maptilerLogo: false,
    };
    
    const mergedOptions = { ...defaultOptions, ...options };
    
    const { style, attributionControl, ...otherOptions } = mergedOptions;
    
    let styleFilters = Array.isArray(style) ? style : false;
    otherOptions.style = Array.isArray(style) ? style : convertStyle(style);
    
    const customNavigationControl = otherOptions.navigationControl;
    otherOptions.navigationControl = false; // Prevent default maptilersdk navigationControl
    
    const mapInstance = new originalMapConstructor(otherOptions);
    mapInstance.initOptions = otherOptions;

    mapInstance.on('load', () => {
		if (styleFilters) {
			mapInstance.addControl(new acmeStyleControl(mapInstance, styleFilters), 'top-right');
		}
		if (customNavigationControl) mapInstance.addControl(new NavigationControl(customNavigationControl), customNavigationControl['position']);
		if (attributionControl) mapInstance.addControl(new CustomAttributionControl({
				compact: true,
		    	autoClose: attributionControl.autoClose,
			}), attributionControl.position);
		if (downloadMapControl) mapInstance.addControl(new downloadMapControl(mapInstance), 'top-left');
    });

    return mapInstance;
};

config.apiKey = process.env.MAPTILER_KEY;

window.whg_maplibre = { Map }
