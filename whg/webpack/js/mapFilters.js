// mapFilters.js

function temporalFilter(baseFilter) {
	if ($('.range_container.expanded').length > 0) { // Is dateline active?
		if ($('#undated_checkbox').is(':checked')) {
			return [ // Include features within the range AND undated features
				'all',
				baseFilter,
				[
					'any',
					[
						'all',
						['!=', 'max', 'null'],
						['!=', 'min', 'null'],
						['>=', 'max', window.dateline.fromValue],
						['<=', 'min', window.dateline.toValue],
					],
					[
						'any',
						['==', 'max', 'null'],
						['==', 'min', 'null']
					]
				]
			]
		}
		else {
			return [ // Include features within the range WITHOUT undated features
				'all',
				baseFilter,
				['has', 'max'],
				['has', 'min'],
				['>=', 'max', window.dateline.fromValue],
				['<=', 'min', window.dateline.toValue],
			]
		}
	}
	else return baseFilter; // No modification - temporal filter is inactive
}

export function toggleFilters(on, mappy, table){
	mappy.getStyle().layers.forEach(layer => {
		if (mappy.layersets.includes(layer.source)) {
			let filter = mappy.getFilter(layer.id); // Base filter is ['==', '$type', geometryType]
			let baseFilter = filter[0] == 'all' ? filter[1] : filter;
			//console.log('Filter switch:', filter, on ? temporalFilter(baseFilter) : baseFilter);
			mappy.setFilter(layer.id, on ? temporalFilter(baseFilter) : baseFilter);
		}
	});
	table.draw();
}
