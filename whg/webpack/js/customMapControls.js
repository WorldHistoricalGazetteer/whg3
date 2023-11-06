import datasetLayers from './mapLayerStyles';

class acmeStyleControl {

	constructor(mappy) {
		this._mappy = mappy;
	}

	onAdd() {
		this._map = this._mappy;
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

class StyleControl {

	constructor(mappy) {
        this._mappy = mappy;
    }

	onAdd() {
		this._map = this._mappy;
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
		    window.additionalLayers.forEach(([sourceId]) => {
		      newSources[sourceId] = previousStyle.sources[sourceId];
		    });
		    const additionalLayers = window.additionalLayers.map(additionalLayer => additionalLayer[1]); // Add any other required sources and layers to window.additionalLayers
		    return {
		      ...nextStyle,
		      sources: newSources,
		      layers: [
		        ...nextStyle.layers,
		        ...previousStyle.layers.filter(layer => datasetLayers.some(dslayer => layer.id.startsWith(dslayer.id) || additionalLayers.includes(layer.id))),
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

export { acmeStyleControl, StyleControl, CustomAttributionControl };