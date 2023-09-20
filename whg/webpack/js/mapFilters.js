export function filteredLayer(layer) {
	if ($('.range_container.expanded').length > 0) { // Is dateline active?
		const modifiedLayer = ({
			...layer
		});
		const existingFilter = modifiedLayer.filter;

		const isUndatedChecked = $('#undated_checkbox').is(':checked');

		if (isUndatedChecked) { // Include features within the range AND undated features
			modifiedLayer.filter = [
				'all',
				existingFilter,
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
			];
		} else { // Include features within the range BUT NOT undated features
			modifiedLayer.filter = [
				'all',
				existingFilter,
				['has', 'max'],
				['has', 'min'],
				['>=', 'max', window.dateline.fromValue],
				['<=', 'min', window.dateline.toValue],
			];
		}

		return modifiedLayer;
	} else return layer;
}

export function toggleFilters(on, mappy, datasetLayers, table){
    datasetLayers.forEach(function(layer){
		mappy.setFilter(layer.id, on ? filteredLayer(layer).filter : layer.filter);
	});
	table.draw();
}

