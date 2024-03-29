// whg_maplibre.js

import Layerset from './layerset';
import { attributionString } from './utilities';

import MapboxDraw from "@mapbox/mapbox-gl-draw";
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css'

import '../css/maplibre-common.css';
import '../css/style-control.css';
import '../css/dateline.css';

maplibregl.Map.prototype.nullCollection = function() {
	return { type: 'FeatureCollection', features: [] }
}

maplibregl.Map.prototype.eraseSource = function(sourceId) {
	var layersToErase = this.getStyle().layers.filter(layer => {return layer.source === sourceId})
	layersToErase.forEach(layer => {
		this.removeLayer(layer.id);
	});
	if (this.getSource(sourceId)) {
		this.removeSource(sourceId);
	}
	return this;
}

maplibregl.Map.prototype.tileBounds = null;
maplibregl.Map.prototype.newSource = function(ds, fc = null) {
    var map = this;
    if (!!ds.tilesets && ds.tilesets.length > 0) {
        const tilejsonUrl = `${process.env.TILEBOSS}/data/${ds.tilesets[0]}.json`;
        $.ajax({
            url: tilejsonUrl,
            dataType: 'json',
            async: false, // Make the AJAX call synchronous
            success: function(tilejson) {
                console.log('tilejson', tilejson);
                const sourceOptions = { ...tilejson, type: 'vector' };
                map.tileBounds = tilejson.bounds;
                map.addSource(ds.ds_id, sourceOptions);
            },
            error: function(xhr, status, error) {
                console.error('Error prefetching TileJSON:', error);
            }
        });
    } else {
        if (!!ds.ds_id) { // Standard dataset or collection
            map.addSource(ds.ds_id, {
                'type': 'geojson',
                'data': ds,
                'attribution': attributionString(ds),
            });
        } else if (fc) { // Name and FeatureCollection provided
            map.addSource(ds, { 'type': 'geojson', 'data': fc });
        } else { // Only name given, add an empty FeatureCollection
            map.addSource(ds, { 'type': 'geojson', 'data': this.nullCollection() });
        }
    }
	return map;
};

// replaced 23 Feb 2024 per SG
// maplibregl.Map.prototype.newSource = function (ds, fc=null) {
//     if (!!ds.tilesets && ds.tilesets.length > 0) {
//         const tilejsonUrl = `${process.env.TILEBOSS}/data/${ds.tilesets[0]}.json`;
//         var map = this;
//         return new Promise((resolve, reject) => {
//             $.ajax({
//                 url: tilejsonUrl,
//                 dataType: 'json',
//                 success: function(tilejson) {
//                     console.log('tilejson', tilejson);
//                     const sourceOptions = { ...tilejson, type: 'vector' };
//                     var source = map.addSource(ds.ds_id, sourceOptions);
//                     map.tileBounds = tilejson.bounds;
//                     resolve(source);
//                 },
//                 error: function(xhr, status, error) {
//                     console.error('Error prefetching TileJSON:', error);
//                     reject(error);
//                 }
//             });
//         });
//     } else {
//         if (!!ds.ds_id) { // Standard dataset or collection
//             return this.addSource(ds.ds_id, {
//                 'type': 'geojson',
//                 'data': ds,
//                 'attribution': attributionString(ds),
//             });
//         } else if (fc) { // Name and FeatureCollection provided
//             return this.addSource(ds, { 'type': 'geojson', 'data': fc });
//         } else { // Only name given, add an empty FeatureCollection
//             return this.addSource(ds, { 'type': 'geojson', 'data': this.nullCollection() });
//         }
//     }
// };

maplibregl.Map.prototype.layersets = [];
maplibregl.Map.prototype.newLayerset = function (dc_id, source_id, paintOption) {
	this.layersets.push(dc_id);
    return new Layerset(this, dc_id, source_id, paintOption);
};

maplibregl.Map.prototype.highlights = [];
maplibregl.Map.prototype.highlight = function (feature) {
	if (this.getFeatureState({source: feature.source, id: feature.id}) !== ({ highlight: true })) {
    	this.setFeatureState({ source: feature.source, id: feature.id }, { highlight: true });
    	this.highlights.push({ source: feature.source, id: feature.id, geometry: feature.geometry });
  	}
}
maplibregl.Map.prototype.clearHighlights = function () {
	this.highlights.forEach(feature => {
		this.setFeatureState({source: feature.source, id: feature.id}, { highlight: false });
	});
	this.highlights = [];
}

function getStyleURL(style) {
	return `${process.env.TILEBOSS}/styles/${style}/style.json`;
}

function getTilejsonURL(style) {
	return `${process.env.TILEBOSS}/data/${style}.json`;
}

async function fetchJSON(jsonURL) {
    try {
        const response = await fetch(jsonURL);
        if (!response.ok) {
            throw new Error(`Failed to fetch JSON. Status: ${response.status}`);
        }
        const resultJSON = await response.json();
        return resultJSON;
    } catch (error) {
        console.error('Error fetching JSON:', error);
        throw error;
    }
}

class acmeStyleControl {

	constructor(mapInstance) {
		this._map = mapInstance;
		this._listContainer = document.getElementById('styleListContainer'); // Hard-coded by template for place_portal page
		this.basemaps = mapInstance.initOptions.basemaps; // e.g. ['natural-earth-1-landcover', 'natural-earth-2-landcover', 'natural-earth-hypsometric-noshade', 'kg-NE2_HR_LC_SR_W', 'kg-NE2_HR_LC_SR_W_DR']
		this.styles = mapInstance.initOptions.styles; // e.g. ['whg-ne-dem']
		this.listDictionary = {};
	}

	onAdd() {
		if (!this._listContainer) {
			this._listContainer = document.createElement('div');
			this._listContainer.className = 'maplibregl-ctrl maplibregl-ctrl-group';
			this._listContainer.textContent = 'Basemap';
			this._listContainer.innerHTML =
				'<button type="button" class="style-button" aria-label="Change basemap style" title="Change basemap style">' +
				'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
				'</button>';
			this._listContainer.querySelector('.style-button').addEventListener('click', this._onClick.bind(this));
		}
		const currentStyle = this._map.getStyle();

        const promises = [
            ...this.basemaps.map(item => fetchJSON(getTilejsonURL(item))),
            ...this.styles.map(item => fetchJSON(getStyleURL(item))),
        ];

        Promise.all(promises)
            .then(results => {
                [...this.basemaps, ...this.styles].forEach((item, index) => {
                    this.listDictionary[item] = results[index];
                });
                this.createMapStyleList();
                this.buildSwitcher(currentStyle);
            })
            .catch(error => {
                console.error('Failed to fetch JSON:', error);
            });

        return this._listContainer.id == 'styleListContainer' ? document.createElement('div') : this._listContainer;
	}

	buildSwitcher(styleJSON) {
		const switches = document.createElement('span');
		switches.id = 'layerSwitches';
        //switches.className = 'maplibre-styles-list';

    	var switchGroups = {};

        for (const layer of styleJSON.layers) {
			if (layer.metadata && layer.metadata['whg:switchgroup']) {
	            const switchGroup = layer.metadata['whg:switchgroup'];
	            if (!switchGroups[switchGroup]) {
	                switchGroups[switchGroup] = [];
	            }
	            switchGroups[switchGroup].push(layer);
	        }
		}

		const sortedGroups = Object.keys(switchGroups).sort();

    	for (const group of sortedGroups) {
			const layers = switchGroups[group];
            layers.sort((a, b) => a.metadata['whg:switchlabel'].localeCompare(b.metadata['whg:switchlabel']));

	        const groupItem = document.createElement('li');
	        groupItem.textContent = group;
	        groupItem.className = 'group-item strong-red';
	        const itemList = document.createElement('ul');
	        itemList.className = 'variant-list';

	        for (const layer of layers) {
	            const itemElement = document.createElement('li');
	            itemElement.className = 'variant-item';

	            const checkbox = document.createElement('input');
	            checkbox.type = 'checkbox';
	            checkbox.dataset.layerId = layer.id;
	            checkbox.checked = layer.layout.visibility === 'visible';
	            checkbox.addEventListener('change', (event) => {
	                this._onSwitcherChange(event);
				});
	            itemElement.appendChild(checkbox);

	            const labelElement = document.createElement('label');
	            labelElement.textContent = layer.metadata['whg:switchlabel'] || layer.id;
	            labelElement.className = 'layer-label';
	            labelElement.dataset.layerId = layer.id;
	            labelElement.addEventListener('click', (event) => {
	                checkbox.checked = !checkbox.checked;
	                this._onSwitcherChange(event);
	            });
	            itemElement.appendChild(labelElement);

	            itemList.appendChild(itemElement);
	        }

	        groupItem.appendChild(itemList);
	        switches.appendChild(groupItem);
	    }

	    const existingSwitches = document.getElementById('layerSwitches');
	    const mapStyleList = document.getElementById('mapStyleList');
	    if (existingSwitches) {
	        mapStyleList.replaceChild(switches, existingSwitches);
	    } else {
	        mapStyleList.appendChild(switches);
	    }

	}

	_onSwitcherChange(event) {
	    const layerId = event.target.dataset.layerId;
	    const layer = this._map.getLayer(layerId);
	    const visibility = this._map.getLayoutProperty(layerId, 'visibility');
	    if (layer) {
	        this._map.setLayoutProperty(layerId, 'visibility', visibility === 'visible' ? 'none' : 'visible');
	    }
	}

    createMapStyleList() {

        var styleList = document.createElement('ul');
        styleList.id = 'mapStyleList';
        styleList.className = 'maplibre-styles-list';

        const groups = [
            { title: 'Basemaps', items: this.basemaps, type: 'basemap' },
            { title: 'Styles', items: this.styles, type: 'style' }
        ];

        for (const [index, group] of groups.entries()) {
            const groupItem = document.createElement('li');
            groupItem.textContent = group.title;
            groupItem.className = 'group-item strong-red';
            const itemList = document.createElement('ul');
            itemList.className = 'variant-list';

            for (const [itemIndex, item] of group.items.entries()) {
                const itemElement = document.createElement('li');
                itemElement.className = 'variant-item';
                itemList.appendChild(itemElement);

                const radioInput = document.createElement('input');
                radioInput.type = 'radio';
                radioInput.name = group.type;
                radioInput.dataset.type = group.type;
                radioInput.dataset.value = item;
                radioInput.checked =
                	(group.type === 'style' && item === this.styles[0]) ||
                	(group.type === 'basemap' && this.listDictionary[this.styles[0]].sources.basemap.url.includes(item));
                radioInput.addEventListener('change', (event) => this._onVariantClick(event));
                itemElement.appendChild(radioInput);

                const labelElement = document.createElement('label');
                labelElement.textContent = this.listDictionary[item].name;
                labelElement.className = 'variant-item-label';
                labelElement.dataset.type = group.type;
                labelElement.dataset.value = item;
                labelElement.addEventListener('click', (event) => {
                    radioInput.checked = true;
                    this._onVariantClick(event);
                });
                itemElement.appendChild(labelElement);

            }

            groupItem.appendChild(itemList);
            styleList.appendChild(groupItem);
        }

	    const horizontalLine = document.createElement('hr');
        horizontalLine.className = 'style-list-divider';
	    styleList.appendChild(horizontalLine);

	    const hillshadeGroupItem = document.createElement('li');
	    hillshadeGroupItem.className = 'group-item';
	    const hillshadeCheckboxItem = document.createElement('li');
	    const hillshadeCheckbox = document.createElement('input');
	    hillshadeCheckbox.type = 'checkbox';
	    hillshadeCheckbox.id = 'hillshadeCheckbox';
        hillshadeCheckbox.className = 'hillshade-checkbox';

        const sources = this.listDictionary[this.styles[0]].sources || {};
		const hasTerrariumSources = Object.keys(sources).some(source => source.startsWith('terrarium'));
	    if (hasTerrariumSources) {
	        hillshadeCheckbox.checked = true;
	    } else {
	        hillshadeCheckbox.disabled = true;
	    }

	    hillshadeCheckbox.addEventListener('change', (event) => this._toggleHillshadeLayers(event));
	    const hillshadeLabel = document.createElement('label');
	    hillshadeLabel.textContent = 'Hillshade';
	    hillshadeLabel.setAttribute('for', 'hillshadeCheckbox');
        hillshadeLabel.className = 'hillshade-label';
	    hillshadeCheckboxItem.appendChild(hillshadeCheckbox);
	    hillshadeCheckboxItem.appendChild(hillshadeLabel);
	    hillshadeGroupItem.appendChild(hillshadeCheckboxItem);
	    styleList.appendChild(hillshadeGroupItem);

        this._listContainer.appendChild(styleList);
    }

	onRemove() {
		this._container.parentNode.removeChild(this._container);
		this._map = undefined;
	}

    _onClick() {
        let styleList = document.getElementById('mapStyleList');
        if (styleList) {
            styleList.classList.toggle('show');
        }
    }

	_toggleHillshadeLayers(event) {
	    const isChecked = event.target.checked;
	    const layers = this._map.getStyle().layers;
	    for (const layer of layers) {
	        if (layer.type == 'hillshade') {
	            this._map.setLayoutProperty(layer.id, 'visibility', isChecked ? 'visible' : 'none');
	        }
	    }
	}

	_onVariantClick(event) {

	    if (event.target.dataset.type === 'basemap') {

			const resultJSON = this.listDictionary[event.target.dataset.value];
	        this._map.setStyle(this._map.getStyle(), {
	            transformStyle: (previousStyle, nextStyle) => ({
	                ...nextStyle,
	                sources: {
	                    ...previousStyle.sources,
	                    'basemap': resultJSON,
	                }
	            })
	        });

		}
		else {

	        const resultJSON = this.listDictionary[event.target.dataset.value];
	        this.buildSwitcher(resultJSON);

			this._map.setStyle(resultJSON, {
	            diff: false, // Force rebuild because native diff logic cannot handle this transformation
	            transformStyle: (previousStyle, nextStyle) => {

					const modifiedSources = {
	                    ...nextStyle.sources,
	                    ...Object.keys(previousStyle.sources).reduce((acc, key) => {
	                        if (!this._map.baseStyle.sources.includes(key)) {
	                            acc[key] = previousStyle.sources[key];
	                        }
	                        return acc;
	                    }, {}),
	                };

	                var modifiedLayers = [
	                    ...nextStyle.layers,
	                    ...previousStyle.layers.filter((layer) => !this._map.baseStyle.layers.includes(layer.id)),
	                ];

	                const hillshadeCheckbox = document.getElementById('hillshadeCheckbox');
	                const isChecked = hillshadeCheckbox ? hillshadeCheckbox.checked : false;
	                for (var layer of modifiedLayers) {
	                    if (layer.type === 'hillshade') {
							layer.layout.visibility = isChecked ? 'visible' : 'none';
	                    }
	                }

	                this._map.baseStyle.sources = Object.keys(resultJSON.sources);
	                this._map.baseStyle.layers = resultJSON.layers.map((layer) => layer.id);

					// Set map container background colour to the value in the style metadata
			        const backgroundColor = resultJSON.metadata['whg:backgroundcolour'];
			        if (backgroundColor) {
			            this._map.getContainer().style.backgroundColor = backgroundColor;
			        }

	                const styleName = resultJSON.sources.basemap.url.split('/').pop().replace('.json', '');
				    const basemapInput = document.querySelector(`input[name="basemap"][value="${styleName}"]`);
			        if (basemapInput) {
			            basemapInput.checked = true;
			        }

					return {
	                    ...nextStyle,
	                    sources: modifiedSources,
	                    layers: modifiedLayers,
	                };
	            },
	        });

		}
	}
}

class CustomTerrainControl {
    constructor(options) {
        this._container = document.createElement('div');
        this._container.className = 'custom-terrain-control maplibregl-ctrl maplibregl-ctrl-group';
        this._terrainSources = [];
        this._currentTerrainSource = null;
        this._tempTerrain = 'temp_terrain';
        this._zoomListener = null;
        this._hillshadeState = null;

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'maplibregl-ctrl-terrain';
        button.title = 'Enable terrain';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'maplibregl-ctrl-icon';
        iconSpan.setAttribute('aria-hidden', 'true');
        button.appendChild(iconSpan);

        button.addEventListener('click', () => this.toggleTerrain(button));
        this._container.appendChild(button);
    }

    onAdd(map) {
        this._map = map;
        return this._container;
    }

    onRemove() {
        this._container.parentNode.removeChild(this._container);
        this._map = undefined;
    }

    toggleTerrain(button) {

        const enablingTerrain = !button.classList.contains('maplibregl-ctrl-terrain-enabled');
        button.classList.toggle('maplibregl-ctrl-terrain-enabled', enablingTerrain);
        button.title = enablingTerrain ? 'Disable terrain' : 'Enable terrain';

        const hillshadeCheckbox = document.getElementById('hillshadeCheckbox');
        if (hillshadeCheckbox) {
	        if (enablingTerrain) {
				this._hillshadeState = hillshadeCheckbox.checked; // Record state of hillshadeCheckbox when terrain is enabled
		        if (!hillshadeCheckbox.checked) {
					hillshadeCheckbox.disabled = false;
					hillshadeCheckbox.click();
		        }
				hillshadeCheckbox.disabled = true;
			}
			else {
				hillshadeCheckbox.disabled = false;
				if (!this._hillshadeState) hillshadeCheckbox.click();
			}
		}

        if (enablingTerrain) {
			const mapStyle = this._map.getStyle();

	        this._terrainSources = [];
            for (const source in mapStyle.sources) {
                const demSource = mapStyle.sources[source];
                if (demSource.type === 'raster-dem') {
                    this._terrainSources.push(demSource);
                }
            }

            this._zoomListener = () => this.handleZoomChange();
            this._map.on('zoom', this._zoomListener);
            this.handleZoomChange();
			this._map.setPitch(60);
		}
		else {
			this._map.off('zoom', this._zoomListener);
            this._zoomListener = null;
            this._terrainSources = [];
			if (this._map.getSource(this._tempTerrain)) {
			    this._map.removeSource(this._tempTerrain);
			}
            this._map
            	.setTerrain(null)
				.setPitch(0)
				.resetNorth();
		}

    }

    handleZoomChange() {
        const currentZoom = this._map.getZoom();

        // TODO: Disable terrain for zoom below 8?

        // Find the first terrain source for which the current map zoom is in range
        const selectedTerrainSource = this._terrainSources.find(source => {
            return currentZoom >= source.minzoom && currentZoom <= source.maxzoom;
        });

        if (selectedTerrainSource && selectedTerrainSource !== this._currentTerrainSource) {
            this._map.setTerrain(null);
			if (this._map.getSource(this._tempTerrain)) {
			    this._map.removeSource(this._tempTerrain);
			}
            this._map.addSource(this._tempTerrain, { ...selectedTerrainSource });
            this._currentTerrainSource = selectedTerrainSource;
            this._map.setTerrain({
                source: this._tempTerrain,
                exaggeration: 1.5,
            });
        }
    }
}

function generateMapImage(map, dpi = 300, fileName = 'WHG_Map') {

	// Create a modal dialog for copyright attribution and acknowledgment
	const modal = $('<div id="map-download-dialog" title="Map Attribution"></div>');
	const injunctionText = $('<div id="injunction-text" class="injunction-text">The following attribution must be displayed together with any use of this map image:</div>');
	const attributionText = $(`<div id="attribution-text" class="attribution-text">${$('.maplibregl-ctrl-attrib-inner').text()}</div>`);
	const downloadButton = $('<button id="download" style="display: none;" disabled>...rendering...</button>');
	const copyAttributionButton = $('<button id="copy-attribution">Acknowledge and Copy Attribution</button>');
	const cancelButton = $('<button id="cancel">Cancel</button>');

	modal.append(injunctionText);
	modal.append(attributionText);
	modal.append(copyAttributionButton);
	modal.append(downloadButton);
	modal.append(cancelButton);

	modal.dialog({
		autoOpen: false,
		appendTo: '#map',
		modal: true,
		width: 'auto',
		buttons: [],
		closeOnEscape: false,
		open: function() {
			new ClipboardJS(copyAttributionButton[0], {
			  text: function(trigger) {
			    return attributionText.text();
			  },
    		  container: document.getElementById('map-download-dialog')
			}).on('success', function(e) {
			  console.log('Attribution text copied to clipboard.');
			  downloadButton.show();
			}).on('error', function(e) {
			  console.error('Unable to copy attribution text: ', e);
			});
		},
		beforeClose: function() {
			renderMap.remove();
			container.remove();
		    Object.defineProperty(window, 'devicePixelRatio', {
			    get: function () {
			      return actualPixelRatio;
			    },
		    });
			console.log('Removed container');
		},
		close: function() {
			modal.remove();
		}
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

	// Create a hidden container for rendering the map
	const originalMapContainer = originalCanvas.parentNode;
	const container = document.createElement('div');
	container.id = 'map-render-container';
	container.style.width = width + 'px';
	container.style.height = height + 'px';
	originalMapContainer.appendChild(container);

	// Create a map renderer
	const renderMap = new maplibregl.Map({
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

	downloadButton.on('click', () => {
		const canvas = renderMap.getCanvas();
		const imageFileName = `${fileName}.png`;

		// Create a download link for the image
		const a = $('<a>');
		a.prop('href', canvas.toDataURL());
		a.prop('download', imageFileName);
		a[0].click();
		a.remove();

		modal.dialog('close');
	});

	cancelButton.on('click', () => {
		modal.dialog('close');
	});

	modal.dialog('open');
}

class downloadMapControl {

	constructor(mapInstance) {
		this._map = mapInstance;
	}

    onAdd() {
        this._container = document.createElement('div');
        this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-download';

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

class CustomAttributionControl extends maplibregl.AttributionControl {
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
				const delay = 500; // Delay required to ensure that listener is registered
                setTimeout(() => {
	                attributionButton.dispatchEvent(new MouseEvent('click', {
	                    bubbles: true,
	                    cancelable: true,
	                    view: window
	                }));
                    container.style.display = 'block';
                    container.classList.add('fade-in');
                }, delay);
            }
        }
        return container;
    }
}

maplibregl.Map.prototype.reset = function () {
	this.flyTo({
		center: this.initOptions.center,
		zoom: this.initOptions.zoom,
        speed: .5,
    });
}

maplibregl.Map.prototype.fitViewport = function (bbox) {
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

class CustomDrawingControl {
	constructor(mapInstance, options) {
		this._map = mapInstance;
		this._options = options;

		this._map._draw = new MapboxDraw({
			displayControlsDefault: false,
			controls: {
				polygon: true,
				trash: true,
			},
		});

		this._map.addControl(this._map._draw, 'top-left');
	}

	onAdd() {
		this._map._drawControl = this._map.getContainer().querySelector(".mapboxgl-ctrl-group.mapboxgl-ctrl");
		this._map._drawControl.classList.add('maplibregl-ctrl', 'maplibregl-ctrl-group'); // Convert classnames for proper rendering
		if (this._options.hide) this._map._drawControl.style.display = 'none';
		return this._map._drawControl;
	}

	onRemove() {
		this._map.removeControl(this._map._draw);
	}
}

const originalMapConstructor = maplibregl.Map;
maplibregl.Map.prototype.baseStyle = {}; // Updated by style control, and used for identifying layers that should be ignored when the map is clicked
maplibregl.Map = function (options = {}) {

    const defaultOptions = {
        container: 'map',
        style: ['whg-basic-light'/*, 'whg-basic-dark'*/],
        basemap: [/*'natural-earth-1-landcover', 'natural-earth-2-landcover', 'natural-earth-hypsometric-noshade'*/],
        zoom: 0.2,
        center: [9.2, 33],
        maxBounds: [[-Infinity, -85], [Infinity, 85]],
        minZoom: 0.1,
        maxZoom: 6,
        maxPitch: 85,
        // Controls (layer control is added depending on number of styles and basemaps listed above)
        attributionControl: {position: 'bottom-right', autoClose: true, customAttribution: '&copy; World Historical Gazetteer & contributors'}, // false
        downloadMapControl: false,
        drawingControl: false, // Instantiate hidden control with {hide: true}
        fullscreenControl: false,
        navigationControl: {position: 'top-right', showZoom: true, showCompass: false, visualizePitch: false}, // false
        sequencerControl: false,
	    temporalControl: false,
	    terrainControl: false, // If true, will force display of full navigation controls too
    };

    // replace defaultOptions with any passed options
    var chosenOptions = { ...defaultOptions, ...options };

    if (chosenOptions.attributionControl) {
		chosenOptions.customAttributionControl = {...chosenOptions.attributionControl, compact: true};
		chosenOptions.attributionControl = false;
	}

    if (chosenOptions.terrainControl) {
		chosenOptions.navigationControl = {position: 'top-right', showZoom: true, showCompass: true, visualizePitch: true};
	}

	chosenOptions.basemaps = chosenOptions.basemap === "" ? [] : (Array.isArray(chosenOptions.basemap) ? chosenOptions.basemap : [chosenOptions.basemap]);

	chosenOptions.styles = [];
	if (!(typeof chosenOptions.style === 'object' && chosenOptions.style !== null && !Array.isArray(chosenOptions.style))) { // style is not JSON object
		chosenOptions.styles = Array.isArray(chosenOptions.style) ? chosenOptions.style : [chosenOptions.style];
		chosenOptions.style = getStyleURL(chosenOptions.styles[0]);
	}

    const mapInstance = new originalMapConstructor(chosenOptions);

    mapInstance.initOptions = chosenOptions;

    mapInstance.on('load', () => { // Add chosen controls

    	const currentStyle = mapInstance.getStyle();
		mapInstance.baseStyle.sources = Object.keys(currentStyle.sources);
		mapInstance.baseStyle.layers = currentStyle.layers.map((layer) => layer.id);

		// Set map container background colour to the value in the style metadata
        const backgroundColor = currentStyle.metadata['whg:backgroundcolour'];
        if (backgroundColor) {
            mapInstance.getContainer().style.backgroundColor = backgroundColor;
        }

		if (chosenOptions.fullscreenControl) mapInstance.addControl(new maplibregl.FullscreenControl(), 'top-left');
		if (chosenOptions.downloadMapControl) mapInstance.addControl(new downloadMapControl(mapInstance), 'top-left');
		if (chosenOptions.drawingControl) mapInstance.addControl(new CustomDrawingControl(mapInstance, chosenOptions.drawingControl), 'top-left');

		if (chosenOptions.basemaps.length + chosenOptions.styles.length > 1) {
			mapInstance.styleControl = new acmeStyleControl( mapInstance );
			mapInstance.addControl(mapInstance.styleControl, 'top-right');
		}
		if (chosenOptions.terrainControl) mapInstance.addControl(new CustomTerrainControl({source: 'terrarium-aws'}), 'top-right');
		if (chosenOptions.navigationControl) mapInstance.addControl(new maplibregl.NavigationControl(chosenOptions.navigationControl), chosenOptions.navigationControl.position);
		if (!!chosenOptions.customAttributionControl) {
			mapInstance.addControl(new CustomAttributionControl(chosenOptions.customAttributionControl), chosenOptions.customAttributionControl.position);
		}
    });
    return mapInstance;
};

window.whg_maplibre = maplibregl;
