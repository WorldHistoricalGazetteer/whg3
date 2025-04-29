// mapFilters.js

export function toggleFilters(on, whg_map, table) {
    whg_map.layersetObjects.forEach(layerset => {
        // Update the temporal filter for this layerset
        if (on) {
            layerset.setTemporalFilter($('#undated_checkbox').is(':checked') ?
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
                ] :
                [
                    'all',
                    ['!=', 'max', 'null'],
                    ['!=', 'min', 'null'],
                    ['>=', 'max', window.dateline.fromValue],
                    ['<=', 'min', window.dateline.toValue],
                ]); // Store the updated temporal filter
        } else {
            layerset.setTemporalFilter(null);  // Reset the temporal filter
        }
    });
    table.draw();
}
