import ClipboardJS from '/webpack/node_modules/clipboard';

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

export function minmaxer(timespans) {
	//console.log('got to minmax()',JSON.stringify(timespans))-->
	starts = [];
	ends = []
	for (t in timespans) {
		// gets 'in', 'earliest' or 'latest'
		starts.push(Object.values(timespans[t].start)[0])
		ends.push(!!timespans[t].end ? Object.values(timespans[t].end)[0] : -1)
	}
	//console.log('starts',starts,'ends',ends)-->
	minmax = [Math.max.apply(null, starts), Math.max.apply(null, ends)]
	return minmax
}

export function startSpinner(spinnerId) {
	const spin_opts = {
		scale: .5,
		top: '50%'
	}
    const newSpinner = new Spin.Spinner(spin_opts).spin();
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
