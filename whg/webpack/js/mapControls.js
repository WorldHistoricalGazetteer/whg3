// /whg/webpack/js/mapControls.js

import Dateline from './dateline';
import generateMapImage from './saveMapImage';
import datasetLayers from './mapLayerStyles';
import { table, scrollToRowByProperty, highlightedFeatureIndex } from './tableFunctions';
import { mappy, ds_list_stats } from './mapAndTable';
import { toggleFilters } from './mapFilters';

let datelineContainer = null;
let additionalLayers = []; // Keep track of added map sources and layers - required for baselayer switching

class fullScreenControl {
	onAdd() { 
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
		this._container.textContent = 'Fullscreen';
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
		this._container.textContent = 'Download image';
		this._container.innerHTML =
			'<button type="button" class="download-map-button" aria-label="Download map image" title="Download map image">' +
			'<span class="maplibregl-ctrl-icon" aria-hidden="true"></span>' +
			'</button>';
		return this._container;
	}
}

class sequencerControl {
	onAdd() {
		this.minSeq = ds_list_stats.seqmin;
        this.maxSeq = ds_list_stats.seqmax;
		console.log(`Sequence range (${ds_list_stats.seqmin}-${ds_list_stats.seqmax}).`);
        if (this.minSeq == this.maxSeq) {
			return;
		}
        
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group sequencer';
		this._container.textContent = 'Explore sequence';
		this._container.innerHTML = '';
		this.currentSeq = this.minSeq;
		this.playing = false;
		this.stepdelay = 3;
        this.playInterval = null;
        
        this.buttons = [
			['skip-first','First waypoint','Already at first waypoint','Disabled during play'],
			['skip-previous','Previous waypoint','Already at first waypoint','Disabled during play'],
			['skip-next','Next waypoint','Already at last waypoint','Disabled during play'],
			['skip-last','Last waypoint','Already at last waypoint','Disabled during play'],
			'separator',
			['play','Play from current waypoint: hold to change speed','Cannot play from last waypoint','Stop playing waypoints']
		];
		
		this.buttons.forEach((button) => {
			this._container.innerHTML += button == 'separator' ? '<span class="separator"/>' : `<button id = "${button[0]}" type="button" style="background-image: url(/static/images/sequencer/${button[0]}-btn.svg)" ${['skip-first', 'skip-previous'].includes(button[0]) ? 'disabled ' : ''}aria-label="${button[1]}" title="${button[1]}" />`
		});
		
		let longClickTimeout;
		let initialisingSlider = false;
		$('body').on('mousedown', '.sequencer:not(.playing) button#play', () => {
		  createSelect.call(this);
		  longClickTimeout = setTimeout(() => {
		      $('#stepDelayDropbox').show();
		      initialisingSlider = true;
		  }, 1000);
		});
		
		$('body').on('mouseup','.sequencer button', (e) => {
		    const sequencer = $('.sequencer');
		    const action = $(e.target).attr('id');
		    
		    if (table.search() !== '') { // Clear any table search filter
				table.search('').draw();
			}
		    
		    console.log(`Sequencer action: ${action} from ${this.currentSeq}.`);
			
			if (highlightedFeatureIndex == undefined) {
				if (['skip-previous', 'skip-next'].includes(action)) { // Highlight feature selected in table
					$('#placetable tr.highlight-row').click();
					return;
				}
				else if (action == 'play' && !initialisingSlider) {
					this.currentSeq -= 1; // Play will commence by re-adding 1
				}
			}
			
			if (action=='play') {
				
		  		clearTimeout(longClickTimeout);
				if (initialisingSlider) {
		  			initialisingSlider = false;
		  			return;
				}
				else {
					$('#stepDelayDropbox').hide();
				    if (!this.playing) {
				        sequencer.addClass('playing');
				        this.startPlayback();
				    } else {
						this.stopPlayback();
				        return;
				    }
				}
			}
			else {
				if (action=='skip-first') {
					this.currentSeq = this.minSeq; 
				}
				else if (action=='skip-previous') {
					this.currentSeq -= 1; 
				}
				else if (action=='skip-next') {
					this.currentSeq += 1; 
				}
				else if (action=='skip-last') {
					this.currentSeq = this.maxSeq; 
				}
				
				scrollToRowByProperty('seq', this.currentSeq);
			}
			
			if (this.playing && this.currentSeq == this.maxSeq) {
				this.stopPlayback();
		        return;
		    }
			this.updateButtons();
			
		});
		
		function createSelect() {
		  if ($('#stepDelayDropbox').length === 0) {
		    const $dropboxContainer = $('<div id="stepDelayDropbox" class="sequencer"></div>');
		    $(this._container).append($dropboxContainer);
		    const $select = $('<select title="Set delay between waypoints" aria-label="Set delay between waypoints"></select>');
		    $dropboxContainer.append($select);
		    for (let i = 1; i <= 20; i++) {
		      const $option = $(`<option value="${i}">${i}s</option>`);
		      $select.append($option);
		    }
		    $select.val(this.stepdelay);
		    $select.on('change', (event) => {
		      const newValue = parseInt(event.target.value);
		      this.stepdelay = newValue;
		    });
		  }
		}

		return this._container;
	}
	
	updateButtons() {
		const sequencer = $('.sequencer');
		this.currentSeq = $('#placetable tr.highlight-row').data('seq');
        if (!this.playing) {
            sequencer.find('button').prop('disabled', false);
            if (this.currentSeq == this.minSeq) {
			    sequencer.find('button#skip-first,button#skip-previous').prop('disabled', true);
			}
			else if (this.currentSeq == this.maxSeq) {
			    sequencer.find('button#skip-last,button#skip-next,button#play').prop('disabled', true);
			}
        } else {
            sequencer.find('button:not(#play)').prop('disabled', true);
        }
        sequencer.find('button').each((i, button) => {
			button.setAttribute('title', this.buttons[i + (i > 3 ? 1 : 0)][button.disabled ? (this.playing ? 3 : 2) : (this.playing && i == 4 ? 3 : 1)]);
			button.setAttribute('aria-label', button.getAttribute('title'));
		});
	}
	
	clickNext() {
		this.currentSeq += 1;
		this.continuePlay = true;
		console.log(`Sequencer action: play ${this.currentSeq}.`);
		scrollToRowByProperty('seq', this.currentSeq); // Triggers updateButtons()
		if (this.currentSeq == this.maxSeq) {
			this.stopPlayback();
		}
	}
		
	startPlayback() {
		console.log('Starting sequence play...');
		this.playing = true;
		$('.sequencer').addClass('playing');
		this.clickNext();
        if (this.currentSeq < this.maxSeq) {
			this.playInterval = setInterval(() => {
				this.clickNext();
	        }, this.stepdelay * 1000);
		}
    }

    stopPlayback() {
        clearInterval(this.playInterval);
        this.playInterval = null;
		this.playing = false;
		$('.sequencer').removeClass('playing');
        this.updateButtons();
		console.log('... stopped sequence play.');
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
		    ds_list.forEach(ds => {
		      newSources[ds.id.toString()] = previousStyle.sources[ds.id.toString()];
		    });
		    additionalLayers.forEach(([sourceId]) => {
		      newSources[sourceId] = previousStyle.sources[sourceId];
		    });
		    const additionalLayerIDs = additionalLayers.map(additionalLayer => additionalLayer[1]); // Add any other required sources and layers to additionalLayers
		    return {
		      ...nextStyle,
		      sources: newSources,
		      layers: [
		        ...nextStyle.layers,
		        ...previousStyle.layers.filter(layer => datasetLayers.some(dslayer => layer.id.startsWith(dslayer.id) || additionalLayerIDs.includes(layer.id))),
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

let mapSequencer;
let datelineInstance = null;
function init_mapControls(){

	if (!!mapParameters.controls.navigation) map.addControl(new maptilersdk.NavigationControl(), 'top-left');
	
	if (mapParameters.styleFilter.length !== 1) {
		mappy.addControl(new StyleControl(mappy), 'top-right');
	}
	
	mappy.addControl(new fullScreenControl(), 'top-left');
	mappy.addControl(new downloadMapControl(), 'top-left');
	
	if (!!mapParameters.controls.sequencer) {
		mapSequencer = new sequencerControl();
		mappy.addControl(mapSequencer, 'bottom-left');
	}
	
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
	        debounceTimeout = setTimeout(toggleFilters(true), 300);
	    }
	    debounceFilterApplication(); 
	}

	if (datelineInstance) {
		datelineInstance.destroy();
		datelineInstance = null;
	}
	if (datelineContainer) {
		datelineContainer.remove();
		datelineContainer = null;
	}

	if (!!mapParameters.controls.temporal) {
		datelineContainer = document.createElement('div');
		datelineContainer.id = 'dateline';
		document.getElementById('mapControls').appendChild(datelineContainer);

		const range = ds_list_stats.max - ds_list_stats.min;
		const buffer = range * 0.1; // 10% buffer

		// Update the temporal settings
		mapParameters.controls.temporal.fromValue = ds_list_stats.min;
		mapParameters.controls.temporal.toValue = ds_list_stats.max;
		mapParameters.controls.temporal.minValue = ds_list_stats.min - buffer;
		mapParameters.controls.temporal.maxValue = ds_list_stats.max + buffer;

		datelineInstance = new Dateline({
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
	            toggleFilters($('.range_container.expanded').length > 0);
	        }
			else if (parentNodeClassList.contains('download-map-button')) {
				generateMapImage(mappy);
			}
			
		}

	});
}

export { init_mapControls, mapSequencer, additionalLayers, datelineInstance };
