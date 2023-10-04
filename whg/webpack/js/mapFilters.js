import datasetLayers from './mapLayerStyles';
import { table } from './tableFunctions';
import { mappy } from './mapAndTable';
import { datelineInstance } from './mapControls';

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
						['>=', 'max', datelineInstance.fromValue],
						['<=', 'min', datelineInstance.toValue],
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
				['>=', 'max', datelineInstance.fromValue],
				['<=', 'min', datelineInstance.toValue],
			];
		}

		return modifiedLayer;
	} else return layer;
}

export function toggleFilters(on){
    datasetLayers.forEach(function(layer){
		ds_list.forEach(function(ds) {
			const modifiedLayer = { ...layer };
		    modifiedLayer.id = `${layer.id}_${ds.id}`;
		    modifiedLayer.source = ds.id.toString();
			mappy.setFilter(modifiedLayer.id, on ? filteredLayer(modifiedLayer).filter : modifiedLayer.filter);
		});
	});
	table.draw();
}

