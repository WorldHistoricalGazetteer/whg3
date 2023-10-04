import {
	bbox
} from './6.5.0_turf.min.js'
import ClipboardJS from '/webpack/node_modules/clipboard';
import {
	lch
} from './chroma.min.js'

export function equidistantLCHColors(numColors) {
	const colors = [];
	const hue_default = 60; // Default red-orange
	const hue_avoid = 150; // Avoid greens (150) or reds (30) for colourblindness
	const hue_avoid_tolerance = 40; // Either side of hue-avoid value
	const hueStep = (360 - hue_avoid_tolerance * 2) / numColors;
	for (let i = 0; i < numColors; i++) {
		const hueValue_raw = hue_default + i * hueStep;
		const hueValue_adjust = hueValue_raw > hue_avoid - hue_avoid_tolerance
		const hueValue_adjusted = hueValue_adjust ? hueValue_raw + hue_avoid_tolerance * 2 : hueValue_raw
		const color = lch(50, 70, hueValue_adjusted % 360).hex();
		colors.push(color);
	}
	return colors;
}

export function arrayColors(strings) {
	if (!Array.isArray(strings)) strings = [];
	strings.reverse().unshift('');
	const numColors = strings.length;
	const colors = equidistantLCHColors(numColors);
	let result = [];
	for (let i = 0; i < numColors; i++) {
		result.push(colors[i]);
		result.push(strings[i]);
	}
	return result.reverse();
}

export function colorTable(arrayColors, target) {
	const colorKeyTable = $('<table>').addClass('color-key-table');
	const tableBody = $('<tbody>');

	for (let i = 0; i < arrayColors.length; i += 2) {
		const label = i == arrayColors.length - 2 ? '<i>no relation</i>' : arrayColors[i];
		const color = arrayColors[i + 1];
		const row = $('<tr>');
		const colorCell = $('<td>').addClass('color-swatch');
		const colorSwatch = $('<div>').addClass('color-swatch');
		colorSwatch.css('background-color', color);
		colorCell.append(colorSwatch);
		const labelCell = $('<td>').html(label);
		row.append(colorCell, labelCell);
		tableBody.append(row);
	}

	colorKeyTable.append(tableBody);
	$(target).append(colorKeyTable);
}

export function initInfoOverlay() {

	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';

	// Initialize checkbox, metadata, and toggle switch, based on isCollapsed
	$('#checkbox').prop('checked', isCollapsed);
	$('#metadata').toggle(!isCollapsed);
	$('#ds_info').toggleClass('info-collapsed', isCollapsed);

	$('#collapseExpand').click(function() {
		$('#metadata').slideToggle(300, function() {
			$('#ds_info').toggleClass('info-collapsed');
		});
	});

	// Update the state when the checkbox is checked
	$('#checkbox').change(function() {
		localStorage.setItem('isCollapsed', $(this).is(':checked'));
	});

}

export function attributionString(data) {
	let attributionParts = [];
	if (data.attribution) {
		attributionParts.push(data.attribution);
	}
	if (data.citation) {
		attributionParts.push(data.citation);
	}
	let attribution = '';
	if (attributionParts.length > 0) attribution = attributionParts.join(', ');

	let attributionStringParts = ['&copy; World Historical Gazetteer & contributors'];
	attributionStringParts.push(data.attribution || data.citation || attribution);

	return attributionStringParts.join(' | ');
}

export function startSpinner(spinnerId = 'dataset_content', scale = .5) {
	// TODO: scale could be set automatically based on size of the container element
	const newSpinner = new Spin.Spinner({
		scale: scale,
		color: '#004080'
	}).spin();
	$((spinnerId.startsWith('.') ? '' : '#') + spinnerId).append(newSpinner.el);
	return newSpinner;
}

export function initUtils(mappy) {

	// activate all tooltips
	$("[rel='tooltip']").tooltip();

	new ClipboardJS('.clippy', {
		text: function(trigger) {
			let target = trigger.getAttribute('data-clipboard-target');
			if (target == null) {
				return trigger.getAttribute('aria-label');
			} else {
				return $(target).text();
			}
		},
		container: document.getElementById('downloadModal') || document.body
	}).on('success', function(e) {
		console.log('clipped')
		e.clearSelection();
		var $trigger = $(e.trigger);
		$trigger.tooltip('dispose').attr('title', 'Copied!').tooltip();
		$trigger.tooltip('show');
		setTimeout(function() {
			$trigger.tooltip('hide');
		}, 2000);
	});

	// image modal
	$("body").on("click", ".pop, #anno_img", function() {
		let image = $(this).is('img') ? $(this) : $(this).find('img:first');
		let url = image.attr('src')
		let txt = image.attr('alt')
		// let re = /(.png|.jpg|.jpeg|.gif|.tif)/g // TODO: Remove if not required
		console.log('url', url)
		$("#header_text").html(txt)
		$('.imagepreview').attr('src', url);
		$('#imageModal').modal('show');
	});
	// TODO: Figure out why the modal close button doesn't work without this additional code:
	$('#imageModal button.close').click(function() {
		$('#imageModal').modal('hide');
	});


	$("clearlines").click(function() {
		mappy.removeLayer('gl_active_poly')
		mappy.removeLayer('outline')
	})

	// for collection description only
	$(".a_more_descrip").click(function() {
		clicked = $(this)
		clicked.hide()
		clicked.parent().find("#dots_descrip").hide()
		clicked.next().show()
		$(".a_less_descrip").show()
	})
	$(".a_less_descrip").click(function() {
		clicked = $(this)
		clicked.hide() // hide 'less' link
		$(".more_descrip").hide() // hide the extra text again
		$("#dots_descrip").show() // show dots again
		$(".a_more_descrip").show() // show more link again
	})

	// Help popups and associated .selector used only in Collection Build pages
	$(".help-matches").click(function() {
		page = $(this).data('id')
		console.log('help:', page)
		$('.selector').dialog('open');
	})

	$(".selector").dialog({
		resizable: false,
		autoOpen: false,
		height: 500,
		width: 700,
		title: "WHG Help",
		modal: true,
		buttons: {
			'Close': function() {
				console.log('close dialog');
				$(this).dialog('close');
			}
		},
		open: function(event, ui) {
			$('#helpme').load('/media/help/' + page + '.html')
		},
		show: {
			effect: "fade",
			duration: 400
		},
		hide: {
			effect: "fade",
			duration: 400
		}
	});

}

export function minmaxer(timespans) {
	let starts = [];
	let ends = []
	for (var t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	return [Math.max.apply(null, starts), Math.max.apply(null, ends)]
}

export function get_ds_list_stats(allFeatures) {
	let min = Infinity;
	let max = -Infinity;
	let seqMin = Infinity;
	let seqMax = -Infinity;
	for (let i = 0; i < allFeatures.length; i++) {
		const featureMin = allFeatures[i].properties.min;
		const featureMax = allFeatures[i].properties.max;
		const seqValue = allFeatures[i].properties.seq;
		if (!isNaN(featureMin) && !isNaN(featureMax)) {
			min = Math.min(min, featureMin);
			max = Math.max(max, featureMax);
		}
		if (!isNaN(seqValue)) {
			seqMin = Math.min(seqMin, seqValue);
			seqMax = Math.max(seqMax, seqValue);
		}
	}
	if (!isFinite(min)) min = -3000;
	if (!isFinite(max)) max = 2000;

	const geojson = {
		"type": "FeatureCollection",
		"features": allFeatures
	};

	return {
		min: min,
		max: max,
		seqmin: seqMin,
		seqmax: seqMax,
		extent: bbox(geojson)
	}
}

let clipboardDetails;
export function clipDetails(items) {
	const detailsObj = {};

	for (const item of items) {
		if (typeof item === 'object' && 'key' in item && 'value' in item) {
			detailsObj[item.key] = item.value;
		}
	}
	detailsObj.timestamp = new Date().toISOString();
	const jsonStr = JSON.stringify(detailsObj);

	const $element = $(`<button id="clipDetails-button" class="clipDetails-button" data-toggle="tooltip" data-placement="bottom" title="Click to copy error log to clipboard" data-clipboard-text='${jsonStr}'>Copy Error Log</button>`);
	$element.tooltip();
	
	if (clipboardDetails) {
    	clipboardDetails.destroy();
    }

	clipboardDetails = new ClipboardJS('#clipDetails-button', {
		text: function(trigger) {
			return trigger.getAttribute('data-clipboard-text');
		},
		container: document.getElementById('detail')
	}).on('success', function(e) {
		e.clearSelection();
		var $trigger = $(e.trigger);
		console.log(`Clipped "${$trigger.attr('data-clipboard-text')}"`);
		$trigger.tooltip('dispose').attr('title', 'Copied!').tooltip();
		$trigger.tooltip('show');
		setTimeout(function() {
			$trigger.tooltip('hide');
		}, 2000);
	});

	return $element;
}