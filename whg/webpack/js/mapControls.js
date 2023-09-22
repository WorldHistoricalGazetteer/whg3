// /whg/webpack/js/mapControls.js

import Dateline from './dateline';
import generateMapImage from './saveMapImage';
import datasetLayers from './mapLayerStyles';

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
	
	constructor(mappy) {
        this._mappy = mappy;
    }
	
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
	
		let mappy = this._mappy;
	
		const variantValue = event.target.dataset.value;
		const style_code = variantValue.split(".");
		console.log('Selected variant: ', variantValue, maptilersdk.MapStyle[style_code[0]][style_code[1]]);
		mappy.setStyle(maptilersdk.MapStyle[style_code[0]][style_code[1]], {
		  transformStyle: (previousStyle, nextStyle) => {
		    const newSources = { ...nextStyle.sources };
		    window.ds_list.forEach(ds => {
		      newSources[ds.id.toString()] = previousStyle.sources[ds.id.toString()];
		    });
		    return {
		      ...nextStyle,
		      sources: newSources,
		      layers: [
		        ...nextStyle.layers,
		        ...previousStyle.layers.filter(layer => datasetLayers.some(dslayer => layer.id.startsWith(dslayer.id)))
		      ]
		    };
		  }
		});

		const styleList = document.getElementById('mapStyleList');
		if (styleList) {
			styleList.classList.remove('show');
		}
	}
}

class CustomAttributionControl extends maptilersdk.AttributionControl {
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

function init_mapControls(mappy, datelineContainer, toggleFilters, mapParameters, table){

	if (!!mapParameters.controls.navigation) map.addControl(new maptilersdk.NavigationControl(), 'top-left');
	
	if (mapParameters.styleFilter.length !== 1) {
		mappy.addControl(new StyleControl(mappy), 'top-right');
	}
	
	mappy.addControl(new fullScreenControl(), 'top-left');
	mappy.addControl(new downloadMapControl(), 'top-left');
	
	mappy.addControl(new CustomAttributionControl({
		compact: true,
    	autoClose: mapParameters.controls.attribution.open === false,
	}), 'bottom-right');

	function dateRangeChanged(fromValue, toValue){
		// Throttle date slider changes using debouncing
		// Ought to be possible to use promises on the `render` event
		let debounceTimeout;
	    function debounceFilterApplication() {
	        clearTimeout(debounceTimeout);
	        debounceTimeout = setTimeout(toggleFilters(true, mappy, table), 300);
	    }
	    debounceFilterApplication(); 
	}

	if (window.dateline) {
		window.dateline.destroy();
		window.dateline = null;
	}
	if (datelineContainer) {
		datelineContainer.remove();
		datelineContainer = null;
	}

	if (!!mapParameters.controls.temporal) {
		datelineContainer = document.createElement('div');
		datelineContainer.id = 'dateline';
		document.getElementById('mapControls').appendChild(datelineContainer);

		const range = window.ds_list_stats.max - window.ds_list_stats.min;
		const buffer = range * 0.1; // 10% buffer

		// Update the temporal settings
		mapParameters.controls.temporal.fromValue = window.ds_list_stats.min;
		mapParameters.controls.temporal.toValue = window.ds_list_stats.max;
		mapParameters.controls.temporal.minValue = window.ds_list_stats.min - buffer;
		mapParameters.controls.temporal.maxValue = window.ds_list_stats.max + buffer;

		window.dateline = new Dateline({
			...mapParameters.controls.temporal,
			onChange: dateRangeChanged
		});
	};
	
	document.addEventListener('click', function(event) {
        
        if (event.target && event.target.parentNode) {
			const parentNodeClassList = event.target.parentNode.classList;
			
			if (parentNodeClassList.contains('maplibregl-ctrl-fullscreen')) {
				console.log('Switching to fullscreen.');
				parentNodeClassList.replace('maplibregl-ctrl-fullscreen', 'maplibregl-ctrl-shrink');
				document.getElementById('mapOverlays').classList.add('fullscreen');
			} 
			else if (parentNodeClassList.contains('maplibregl-ctrl-shrink')) {
				console.log('Switching off fullscreen.');
				parentNodeClassList.replace('maplibregl-ctrl-shrink', 'maplibregl-ctrl-fullscreen');
				document.getElementById('mapOverlays').classList.remove('fullscreen');
			}
			else if (parentNodeClassList.contains('dateline-button')) {
	            toggleFilters($('.range_container.expanded').length > 0, mappy, table);
	        }
			else if (parentNodeClassList.contains('download-map-button')) {
				generateMapImage(mappy);
			}
			
		}

	});
	
	return { datelineContainer, mapParameters }
	
}

export { init_mapControls };
