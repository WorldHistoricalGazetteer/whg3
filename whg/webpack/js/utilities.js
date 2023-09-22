import { bbox } from './6.5.0_turf.min.js'
import ClipboardJS from '/webpack/node_modules/clipboard';

export function initInfoOverlay() {
	
	var isCollapsed = localStorage.getItem('isCollapsed') === 'true';
	
	// Initialize checkbox, metadata, and toggle switch, based on isCollapsed
    $('#checkbox').prop('checked', isCollapsed);
	$('#metadata').toggle(!isCollapsed);
	$('#ds_info').toggleClass('info-collapsed', isCollapsed);

	$('#collapseExpand').click(function() {
		$('#metadata').slideToggle(300, function(){ $('#ds_info').toggleClass('info-collapsed'); });
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

export function startSpinner(spinnerId = 'body', scale = .5) {
	// TODO: scale could be set automatically based on size of the container element
    const newSpinner = new Spin.Spinner({scale: scale, color: '#004080'}).spin();
    $("#" + spinnerId).append(newSpinner.el);
    return newSpinner;
}

export function initUtils(mappy){
	
	// activate all tooltips
	$("[rel='tooltip']").tooltip();
	
	var clip_cite = new ClipboardJS('#a_clipcite');
	clip_cite.on('success', function(e) {
		console.log('clipped')
		e.clearSelection();
		$("#a_clipcite").tooltip('hide')
			.attr('data-original-title', 'copied!')
			.tooltip('show');
	});
	
	$("clearlines").click(function() {
		mappy.removeLayer('gl_active_poly')
		mappy.removeLayer('outline')
	})
	
}

export function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))-->
	let starts = [];
	let ends = []
	for (var t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)-->
	return [Math.max.apply(null, starts), Math.max.apply(null, ends)]
}

export function get_ds_list_stats(allFeatures) {
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < allFeatures.length; i++) {
        const featureMin = allFeatures[i].properties.min;
        const featureMax = allFeatures[i].properties.max;
        if (!isNaN(featureMin) && !isNaN(featureMax)) {
            min = Math.min(min, featureMin);
            max = Math.max(max, featureMax);
        }
    }
    if (!isFinite(min)) min = -3000;
	if (!isFinite(max)) max = 2000;
    
    const geojson = {
	    "type": "FeatureCollection",
	    "features": allFeatures
	};
	
	return {min: min, max: max, extent: bbox(geojson)}
}