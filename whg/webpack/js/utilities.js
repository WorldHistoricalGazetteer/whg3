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
