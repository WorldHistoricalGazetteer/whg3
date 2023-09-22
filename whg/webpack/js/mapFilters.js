import datasetLayers from './mapLayerStyles';

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

export function toggleFilters(on, mappy, table){
    datasetLayers.forEach(function(layer){
		window.ds_list.forEach(function(ds) {
			const modifiedLayer = { ...layer };
		    modifiedLayer.id = `${layer.id}_${ds.id}`;
		    modifiedLayer.source = ds.id.toString();
			mappy.setFilter(modifiedLayer.id, on ? filteredLayer(modifiedLayer).filter : modifiedLayer.filter);
		});
	});
	table.draw();
}

