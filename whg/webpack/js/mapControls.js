// /whg/webpack/js/mapControls.js

import Dateline from './dateline';
import generateMapImage from './saveMapImage';
import throttle from 'lodash/throttle';
import { table } from './tableFunctions';
import { scrollToRowByProperty } from './tableFunctions-extended';

class fullScreenControl {
	onAdd() {
		this._map = map;
		this._container = document.createElement('div');
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-fullscreen';
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
		this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group maplibregl-ctrl-download';
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
		this.minSeq = 0; //window.ds_list_stats.seqmin;
        this.maxSeq = window.ds_list_stats.count - 1; //window.ds_list_stats.seqmax;
		console.log(`Sequence range (${this.minSeq}-${this.maxSeq}).`);
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
        this.sortedPIDs = [];

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

			if (window.highlightedFeatureIndex == undefined) {
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

				scrollToRowByProperty(table, 'pid', this.sortedPIDs[this.currentSeq]);
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
		
		const highlightedPid = $('#placetable tr.highlight-row').attr('pid');
		this.currentSeq = this.sortedPIDs.indexOf(parseInt(highlightedPid));
		
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
		scrollToRowByProperty(table, 'pid', this.sortedPIDs[this.currentSeq]); // Triggers updateButtons()
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
    
    toggle(show) {
        this.stopPlayback();
        if (show === undefined) {
            this._container.style.display = this._container.style.display === 'none' ? 'flex' : 'none';
        } else {
            if (!show) {
                this._container.style.display = 'none';
            } else {
                this._container.style.display = 'flex';
            }
        }
      	if (this._container.style.display === 'flex') {
			// Update sortedPIDs to match current table sort order
			mapSequencer.sortedPIDs = table.rows({ order: 'current' }).data().map(rowData => rowData.properties.pid);
		}
    }
}

let mapSequencer;
function init_mapControls(mappy, datelineContainer, toggleFilters, mapParameters, table){

	mappy.addControl(new fullScreenControl(), 'top-left');
	mappy.addControl(new downloadMapControl(), 'top-left');

	if (!!mapParameters.controls.sequencer) {
		mapSequencer = new sequencerControl();
		mappy.addControl(mapSequencer, 'bottom-left');
	}
			
	const dateRangeChanged = throttle(() => { // Uses imported lodash function
	    toggleFilters(true, mappy, table);
	}, 300);

	if (window.dateline) {
		window.dateline.destroy();
		window.dateline = null;
	}
	if (datelineContainer) {
		datelineContainer.remove();
		datelineContainer = null;
	}

	if (!!mapParameters.temporalControl) {
		datelineContainer = document.createElement('div');
		datelineContainer.id = 'dateline';
		document.getElementById('mapControls').appendChild(datelineContainer);

		const range = window.ds_list_stats.max - window.ds_list_stats.min;
		const buffer = range * 0.1; // 10% buffer

		// Update the temporal settings
		mapParameters.temporalControl.fromValue = window.ds_list_stats.min;
		mapParameters.temporalControl.toValue = window.ds_list_stats.max;
		mapParameters.temporalControl.minValue = Math.floor(window.ds_list_stats.min - buffer);
		mapParameters.temporalControl.maxValue = Math.ceil(window.ds_list_stats.max + buffer);

		window.dateline = new Dateline({
			...mapParameters.temporalControl,
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

	return { datelineContainer, mapParameters, mapSequencer }

}

export { init_mapControls, mapSequencer };
